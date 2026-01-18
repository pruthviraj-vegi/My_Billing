import logging
from functools import lru_cache
from typing import BinaryIO, Tuple
from urllib.parse import urlparse
from enum import Enum

import boto3
import botocore.exceptions
from botocore.config import Config
from decouple import config

logger = logging.getLogger(__name__)


class BucketType(Enum):
    """Enum for supported bucket types."""

    INVOICE = "invoice"
    STATEMENT = "statement"


class R2StorageError(Exception):
    """Custom exception for R2 storage operations."""

    pass


@lru_cache(maxsize=1)
def get_r2_client() -> boto3.client:
    """
    Get a cached R2 client instance with retry configuration.

    Returns:
        boto3.client: Configured R2 S3-compatible client

    Raises:
        R2StorageError: If required credentials are missing
    """
    try:
        r2_access_key = config("R2_ACCESS_KEY")
        r2_secret_key = config("R2_SECRET_KEY")
        r2_endpoint = config("R2_ENDPOINT")
        r2_region = config("R2_REGION", default="auto")
    except Exception as e:
        raise R2StorageError(
            f"Missing required R2 credentials in environment: {str(e)}"
        )

    # Configure retry strategy
    boto_config = Config(
        retries={"max_attempts": 3, "mode": "adaptive"},
        connect_timeout=5,
        read_timeout=10,
    )

    session = boto3.session.Session()
    return session.client(
        "s3",
        aws_access_key_id=r2_access_key,
        aws_secret_access_key=r2_secret_key,
        endpoint_url=r2_endpoint,
        region_name=r2_region,
        config=boto_config,
    )


def get_bucket_info(
    bucket_type: BucketType, use_custom_domain: bool = False
) -> Tuple[str, str]:
    """
    Get bucket name and domain URL for the specified bucket type.

    Args:
        bucket_type: Type of bucket (BucketType enum)
        use_custom_domain: If True, use custom domain. If False, use R2.dev public domain.

    Returns:
        Tuple of (bucket_name, domain_url)

    Raises:
        R2StorageError: If required environment variables are missing
    """
    # Keep the bucket type value as-is for the bucket name (e.g., "invoice" not "INVOICE")
    # But use uppercase for environment variable names
    bucket_type_value = bucket_type.value  # "invoice" or "statement"
    bucket_type_upper = bucket_type_value.upper()  # "INVOICE" or "STATEMENT"

    bucket_env = f"R2_{bucket_type_upper}_BUCKET"

    try:
        bucket_name = config(bucket_env)
    except Exception:
        raise R2StorageError(f"Missing environment variable: {bucket_env}")

    if use_custom_domain:
        domain_env = f"{bucket_type_upper}_DOMAIN"
        try:
            domain_url = config(domain_env)
        except Exception:
            raise R2StorageError(f"Missing environment variable: {domain_env}")
    else:
        # Use Cloudflare R2.dev public domain
        r2_dev_url_env = f"R2_{bucket_type_upper}_PUBLIC_URL"
        try:
            domain_url = config(r2_dev_url_env)
        except Exception:
            raise R2StorageError(
                f"Missing environment variable: {r2_dev_url_env}. "
                f"This should be your R2 bucket's public URL (e.g., https://pub-xxxxx.r2.dev)"
            )

    return bucket_name, domain_url


def extract_filename_from_url(file_url: str) -> str:
    """
    Extract filename from URL safely.

    Args:
        file_url: Full URL of the file

    Returns:
        Extracted filename

    Raises:
        ValueError: If URL is invalid or filename cannot be extracted
    """
    if not file_url:
        raise ValueError("file_url cannot be empty")

    try:
        parsed = urlparse(file_url)
        filename = parsed.path.rstrip("/").split("/")[-1]

        if not filename:
            raise ValueError(f"Could not extract filename from URL: {file_url}")

        return filename
    except Exception as e:
        raise ValueError(f"Invalid URL format: {file_url}") from e


def delete_from_r2(
    file_url: str,
    bucket_type: BucketType = BucketType.INVOICE,
    use_custom_domain: bool = False,
) -> bool:
    """
    Delete a file from R2 storage.

    Args:
        file_url: The URL of the file to delete
        bucket_type: Type of bucket (defaults to INVOICE)
        use_custom_domain: Whether the URL uses custom domain (defaults to False)

    Returns:
        True if deletion was successful or file doesn't exist, False on error
    """
    try:
        client = get_r2_client()
        bucket_name, _ = get_bucket_info(bucket_type, use_custom_domain)
        filename = extract_filename_from_url(file_url)

        client.delete_object(Bucket=bucket_name, Key=filename)
        logger.info(
            f"Successfully deleted file '{filename}' from '{bucket_type.value}' bucket"
        )
        return True

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "404" or error_code == "NoSuchKey":
            logger.warning(
                f"File '{filename}' not found in '{bucket_type.value}' bucket "
                "(already deleted or never existed)"
            )
            return True

        logger.error(
            f"AWS error deleting file '{filename}' from '{bucket_type.value}': "
            f"{error_code} - {str(e)}"
        )
        return False

    except R2StorageError as e:
        logger.error(f"R2 configuration error: {str(e)}")
        return False

    except Exception as e:
        logger.error(
            f"Unexpected error deleting file from '{bucket_type.value}' bucket: "
            f"{type(e).__name__}: {str(e)}"
        )
        return False


def upload_pdf_to_r2(
    file_obj: BinaryIO,
    filename: str,
    bucket_type: BucketType = BucketType.INVOICE,
    make_public: bool = True,
    use_custom_domain: bool = False,
) -> str:
    """
    Upload a PDF file to R2 storage.

    Args:
        file_obj: File-like object to upload (must be open for reading in binary mode)
        filename: Name to save the file as in R2
        bucket_type: Type of bucket (defaults to INVOICE)
        make_public: Whether to make the file publicly readable
        use_custom_domain: If True, return custom domain URL. If False, return R2 public URL.

    Returns:
        Public URL of the uploaded file

    Raises:
        R2StorageError: If upload fails or configuration is invalid
        ValueError: If filename is invalid
    """
    if not filename:
        raise ValueError("filename cannot be empty")

    if not filename.lower().endswith(".pdf"):
        logger.warning(f"Filename '{filename}' doesn't end with .pdf")

    try:
        client = get_r2_client()
        bucket_name, domain_url = get_bucket_info(bucket_type, use_custom_domain)

        # Ensure file pointer is at the beginning
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        # Prepare upload arguments
        extra_args = {"ContentType": "application/pdf"}
        if make_public:
            extra_args["ACL"] = "public-read"

        # Upload to R2
        client.upload_fileobj(
            Fileobj=file_obj,
            Bucket=bucket_name,
            Key=filename,
            ExtraArgs=extra_args,
        )

        file_url = f"{domain_url.rstrip('/')}/{filename}"
        logger.info(
            f"Successfully uploaded '{filename}' to '{bucket_type.value}' bucket"
        )
        return file_url

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = f"AWS error uploading '{filename}': {error_code} - {str(e)}"
        logger.error(error_msg)
        raise R2StorageError(error_msg) from e

    except R2StorageError:
        raise

    except Exception as e:
        error_msg = (
            f"Unexpected error uploading '{filename}' to '{bucket_type.value}': "
            f"{type(e).__name__}: {str(e)}"
        )
        logger.error(error_msg)
        raise R2StorageError(error_msg) from e


def check_file_exists(
    file_url: str,
    bucket_type: BucketType = BucketType.INVOICE,
    use_custom_domain: bool = False,
) -> bool:
    """
    Check if a file exists in R2 storage.

    Args:
        file_url: The URL of the file to check
        bucket_type: Type of bucket (defaults to INVOICE)
        use_custom_domain: Whether the URL uses custom domain (defaults to False)

    Returns:
        True if file exists, False otherwise
    """
    try:
        client = get_r2_client()
        bucket_name, _ = get_bucket_info(bucket_type, use_custom_domain)
        filename = extract_filename_from_url(file_url)

        client.head_object(Bucket=bucket_name, Key=filename)
        logger.info(f"File '{filename}' exists in '{bucket_type.value}' bucket")
        return True

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "404" or error_code == "NoSuchKey":
            logger.debug(f"File '{filename}' not found in '{bucket_type.value}' bucket")
            return False

        logger.error(
            f"Error checking file '{filename}' in '{bucket_type.value}': "
            f"{error_code} - {str(e)}"
        )
        return False

    except R2StorageError as e:
        logger.error(f"R2 configuration error: {str(e)}")
        return False

    except Exception as e:
        logger.error(
            f"Unexpected error checking file existence: "
            f"{type(e).__name__}: {str(e)}"
        )
        return False


def get_file_metadata(
    file_url: str,
    bucket_type: BucketType = BucketType.INVOICE,
    use_custom_domain: bool = False,
) -> dict:
    """
    Get metadata for a file in R2 storage.

    Args:
        file_url: The URL of the file
        bucket_type: Type of bucket (defaults to INVOICE)
        use_custom_domain: Whether the URL uses custom domain (defaults to False)

    Returns:
        Dictionary containing file metadata (size, content-type, etc.)
        Empty dict if file doesn't exist or error occurs
    """
    try:
        client = get_r2_client()
        bucket_name, _ = get_bucket_info(bucket_type, use_custom_domain)
        filename = extract_filename_from_url(file_url)

        response = client.head_object(Bucket=bucket_name, Key=filename)

        metadata = {
            "content_length": response.get("ContentLength", 0),
            "content_type": response.get("ContentType", ""),
            "last_modified": response.get("LastModified"),
            "etag": response.get("ETag", "").strip('"'),
        }

        logger.info(f"Retrieved metadata for '{filename}'")
        return metadata

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404" or error_code == "NoSuchKey":
            logger.warning(f"File '{filename}' not found")
        else:
            logger.error(f"Error getting metadata: {str(e)}")
        return {}

    except Exception as e:
        logger.error(f"Unexpected error getting metadata: {str(e)}")
        return {}
