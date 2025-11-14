// Color database with common colors
const colorDatabase = {
    // Reds
    'Red': '#FF0000',
    'Crimson': '#DC143C',
    'Dark Red': '#8B0000',
    'Fire Brick': '#B22222',
    'Indian Red': '#CD5C5C',
    'Light Coral': '#F08080',
    'Salmon': '#FA8072',
    'Dark Salmon': '#E9967A',
    'Light Salmon': '#FFA07A',

    // Blues
    'Blue': '#0000FF',
    'Navy': '#000080',
    'Dark Blue': '#00008B',
    'Medium Blue': '#0000CD',
    'Royal Blue': '#4169E1',
    'Steel Blue': '#4682B4',
    'Dodger Blue': '#1E90FF',
    'Deep Sky Blue': '#00BFFF',
    'Light Blue': '#ADD8E6',
    'Sky Blue': '#87CEEB',
    'Light Sky Blue': '#87CEFA',
    'Midnight Blue': '#191970',
    'Navy Blue': '#000080',

    // Greens
    'Green': '#008000',
    'Dark Green': '#006400',
    'Forest Green': '#228B22',
    'Lime': '#00FF00',
    'Lime Green': '#32CD32',
    'Light Green': '#90EE90',
    'Pale Green': '#98FB98',
    'Dark Sea Green': '#8FBC8F',
    'Medium Spring Green': '#00FA9A',
    'Spring Green': '#00FF7F',
    'Sea Green': '#2E8B57',
    'Medium Sea Green': '#3CB371',
    'Light Sea Green': '#20B2AA',

    // Yellows
    'Yellow': '#FFFF00',
    'Gold': '#FFD700',
    'Light Yellow': '#FFFFE0',
    'Lemon Chiffon': '#FFFACD',
    'Light Goldenrod Yellow': '#FAFAD2',
    'Papaya Whip': '#FFEFD5',
    'Moccasin': '#FFE4B5',
    'Peach Puff': '#FFDAB9',
    'Pale Goldenrod': '#EEE8AA',
    'Khaki': '#F0E68C',
    'Dark Khaki': '#BDB76B',

    // Oranges
    'Orange': '#FFA500',
    'Dark Orange': '#FF8C00',
    'Orange Red': '#FF4500',
    'Tomato': '#FF6347',
    'Coral': '#FF7F50',
    'Light Coral': '#F08080',
    'Dark Salmon': '#E9967A',
    'Salmon': '#FA8072',
    'Light Salmon': '#FFA07A',

    // Purples
    'Purple': '#800080',
    'Dark Purple': '#483D8B',
    'Medium Purple': '#9370DB',
    'Blue Violet': '#8A2BE2',
    'Dark Violet': '#9400D3',
    'Dark Orchid': '#9932CC',
    'Medium Orchid': '#BA55D3',
    'Medium Slate Blue': '#7B68EE',
    'Slate Blue': '#6A5ACD',
    'Dark Slate Blue': '#483D8B',
    'Medium Violet Red': '#C71585',
    'Violet Red': '#D02090',
    'Magenta': '#FF00FF',
    'Violet': '#EE82EE',
    'Plum': '#DDA0DD',
    'Orchid': '#DA70D6',
    'Medium Orchid': '#BA55D3',
    'Dark Orchid': '#9932CC',
    'Dark Violet': '#9400D3',
    'Blue Violet': '#8A2BE2',
    'Purple': '#800080',
    'Indigo': '#4B0082',
    'Dark Slate Blue': '#483D8B',
    'Slate Blue': '#6A5ACD',
    'Medium Slate Blue': '#7B68EE',

    // Browns
    'Brown': '#A52A2A',
    'Maroon': '#800000',
    'Saddle Brown': '#8B4513',
    'Sienna': '#A0522D',
    'Chocolate': '#D2691E',
    'Dark Goldenrod': '#B8860B',
    'Peru': '#CD853F',
    'Rosy Brown': '#BC8F8F',
    'Goldenrod': '#DAA520',
    'Tan': '#D2B48C',
    'Burlywood': '#DEB887',
    'Wheat': '#F5DEB3',
    'Navajo White': '#FFDEAD',
    'Bisque': '#FFE4C4',
    'Blanched Almond': '#FFEBCD',
    'Cornsilk': '#FFF8DC',

    // Grays
    'Gray': '#808080',
    'Grey': '#808080',
    'Dim Gray': '#696969',
    'Dim Grey': '#696969',
    'Light Gray': '#D3D3D3',
    'Light Grey': '#D3D3D3',
    'Silver': '#C0C0C0',
    'Dark Gray': '#A9A9A9',
    'Dark Grey': '#A9A9A9',
    'Gainsboro': '#DCDCDC',
    'Light Steel Blue': '#B0C4DE',
    'Light Slate Gray': '#778899',
    'Light Slate Grey': '#778899',
    'Slate Gray': '#708090',
    'Slate Grey': '#708090',
    'Dark Slate Gray': '#2F4F4F',
    'Dark Slate Grey': '#2F4F4F',

    // Whites
    'White': '#FFFFFF',
    'Snow': '#FFFAFA',
    'Honeydew': '#F0FFF0',
    'Mint Cream': '#F5FFFA',
    'Azure': '#F0FFFF',
    'Alice Blue': '#F0F8FF',
    'Ghost White': '#F8F8FF',
    'White Smoke': '#F5F5F5',
    'Seashell': '#FFF5EE',
    'Beige': '#F5F5DC',
    'Old Lace': '#FDF5E6',
    'Floral White': '#FFFAF0',
    'Ivory': '#FFFFF0',
    'Antique White': '#FAEBD7',
    'Linen': '#FAF0E6',
    'Lavender Blush': '#FFF0F5',
    'Misty Rose': '#FFE4E1',

    // Blacks
    'Black': '#000000',
    'Dark Slate Gray': '#2F4F4F',
    'Dim Gray': '#696969',
    'Slate Gray': '#708090',
    'Light Slate Gray': '#778899',
    'Gray': '#808080',
    'Light Gray': '#D3D3D3',
    'Midnight Blue': '#191970',
    'Navy': '#000080',
    'Cornflower Blue': '#6495ED',
    'Dark Slate Blue': '#483D8B',
    'Slate Blue': '#6A5ACD',
    'Medium Slate Blue': '#7B68EE',
    'Light Slate Blue': '#8470FF',
    'Medium Blue': '#0000CD',
    'Royal Blue': '#4169E1',
    'Blue': '#0000FF',
    'Dodger Blue': '#1E90FF',
    'Deep Sky Blue': '#00BFFF',
    'Sky Blue': '#87CEEB',
    'Light Sky Blue': '#87CEFA',
    'Steel Blue': '#4682B4',
    'Light Steel Blue': '#B0C4DE',
    'Light Blue': '#ADD8E6',
    'Powder Blue': '#B0E0E6',
    'Light Cyan': '#E0FFFF',
    'Cyan': '#00FFFF',
    'Aqua': '#00FFFF',
    'Turquoise': '#40E0D0',
    'Medium Turquoise': '#48D1CC',
    'Dark Turquoise': '#00CED1',
    'Aquamarine': '#7FFFD4',
    'Pale Turquoise': '#AFEEEE',
    'Light Cyan': '#E0FFFF',
    'Azure': '#F0FFFF',
    'Light Azure': '#E0F8FF',
    'Alice Blue': '#F0F8FF',
    'Ghost White': '#F8F8FF',
    'White Smoke': '#F5F5F5',
    'Seashell': '#FFF5EE',
    'Floral White': '#FFFAF0',
    'Lavender': '#E6E6FA',
    'Thistle': '#D8BFD8',
    'Plum': '#DDA0DD',
    'Violet': '#EE82EE',
    'Orchid': '#DA70D6',
    'Fuchsia': '#FF00FF',
    'Magenta': '#FF00FF',
    'Medium Orchid': '#BA55D3',
    'Medium Purple': '#9370DB',
    'Blue Violet': '#8A2BE2',
    'Dark Violet': '#9400D3',
    'Dark Orchid': '#9932CC',
    'Dark Magenta': '#8B008B',
    'Purple': '#800080',
    'Indigo': '#4B0082',
    'Dark Slate Blue': '#483D8B',
    'Slate Blue': '#6A5ACD',
    'Medium Slate Blue': '#7B68EE',
    'Green Yellow': '#ADFF2F',
    'Chartreuse': '#7FFF00',
    'Lawn Green': '#7CFC00',
    'Lime': '#00FF00',
    'Lime Green': '#32CD32',
    'Pale Green': '#98FB98',
    'Light Green': '#90EE90',
    'Medium Spring Green': '#00FA9A',
    'Spring Green': '#00FF7F',
    'Medium Sea Green': '#3CB371',
    'Sea Green': '#2E8B57',
    'Forest Green': '#228B22',
    'Green': '#008000',
    'Dark Green': '#006400',
    'Yellow Green': '#9ACD32',
    'Olive Drab': '#6B8E23',
    'Olive': '#808000',
    'Dark Olive Green': '#556B2F',
    'Medium Aquamarine': '#66CDAA',
    'Dark Sea Green': '#8FBC8F',
    'Light Sea Green': '#20B2AA',
    'Dark Cyan': '#008B8B',
    'Teal': '#008080',
    'Dark Slate Gray': '#2F4F4F',
    'Dark Slate Grey': '#2F4F4F',
    'Medium Turquoise': '#48D1CC',
    'Light Sea Green': '#20B2AA',
    'Pale Turquoise': '#AFEEEE',
    'Aquamarine': '#7FFFD4',
    'Powder Blue': '#B0E0E6',
    'Light Blue': '#ADD8E6',
    'Sky Blue': '#87CEEB',
    'Light Sky Blue': '#87CEFA',
    'Steel Blue': '#4682B4',
    'Light Steel Blue': '#B0C4DE',
    'Light Gray': '#D3D3D3',
    'Light Grey': '#D3D3D3',
    'Gainsboro': '#DCDCDC',
    'White Smoke': '#F5F5F5',
    'White': '#FFFFFF',
    'Snow': '#FFFAFA',
    'Honeydew': '#F0FFF0',
    'Mint Cream': '#F5FFFA',
    'Azure': '#F0FFFF',
    'Alice Blue': '#F0F8FF',
    'Ghost White': '#F8F8FF',
    'Seashell': '#FFF5EE',
    'Beige': '#F5F5DC',
    'Old Lace': '#FDF5E6',
    'Floral White': '#FFFAF0',
    'Ivory': '#FFFFF0',
    'Antique White': '#FAEBD7',
    'Linen': '#FAF0E6',
    'Lavender Blush': '#FFF0F5',
    'Misty Rose': '#FFE4E1',
    'Black': '#000000',
    'Dark Slate Gray': '#2F4F4F',
    'Dim Gray': '#696969',
    'Dim Grey': '#696969',
    'Slate Gray': '#708090',
    'Slate Grey': '#708090',
    'Light Slate Gray': '#778899',
    'Light Slate Grey': '#778899',
    'Gray': '#808080',
    'Grey': '#808080',
    'Light Gray': '#D3D3D3',
    'Light Grey': '#D3D3D3',
    'Midnight Blue': '#191970',
    'Navy': '#000080',
    'Cornflower Blue': '#6495ED',
    'Dark Slate Blue': '#483D8B',
    'Slate Blue': '#6A5ACD',
    'Medium Slate Blue': '#7B68EE',
    'Light Slate Blue': '#8470FF',
    'Medium Blue': '#0000CD',
    'Royal Blue': '#4169E1',
    'Blue': '#0000FF',
    'Dodger Blue': '#1E90FF',
    'Deep Sky Blue': '#00BFFF',
    'Sky Blue': '#87CEEB',
    'Light Sky Blue': '#87CEFA',
    'Steel Blue': '#4682B4',
    'Light Steel Blue': '#B0C4DE',
    'Light Blue': '#ADD8E6',
    'Powder Blue': '#B0E0E6',
    'Light Cyan': '#E0FFFF',
    'Cyan': '#00FFFF',
    'Aqua': '#00FFFF',
    'Turquoise': '#40E0D0',
    'Medium Turquoise': '#48D1CC',
    'Dark Turquoise': '#00CED1',
    'Aquamarine': '#7FFFD4',
    'Pale Turquoise': '#AFEEEE',
    'Light Cyan': '#E0FFFF',
    'Azure': '#F0FFFF',
    'Light Azure': '#E0F8FF',
    'Alice Blue': '#F0F8FF',
    'Ghost White': '#F8F8FF',
    'White Smoke': '#F5F5F5',
    'Seashell': '#FFF5EE',
    'Floral White': '#FFFAF0',
    'Lavender': '#E6E6FA',
    'Thistle': '#D8BFD8',
    'Plum': '#DDA0DD',
    'Violet': '#EE82EE',
    'Orchid': '#DA70D6',
    'Fuchsia': '#FF00FF',
    'Magenta': '#FF00FF',
    'Medium Orchid': '#BA55D3',
    'Medium Purple': '#9370DB',
    'Blue Violet': '#8A2BE2',
    'Dark Violet': '#9400D3',
    'Dark Orchid': '#9932CC',
    'Dark Magenta': '#8B008B',
    'Purple': '#800080',
    'Indigo': '#4B0082',
    'Dark Slate Blue': '#483D8B',
    'Slate Blue': '#6A5ACD',
    'Medium Slate Blue': '#7B68EE',
    'Green Yellow': '#ADFF2F',
    'Chartreuse': '#7FFF00',
    'Lawn Green': '#7CFC00',
    'Lime': '#00FF00',
    'Lime Green': '#32CD32',
    'Pale Green': '#98FB98',
    'Light Green': '#90EE90',
    'Medium Spring Green': '#00FA9A',
    'Spring Green': '#00FF7F',
    'Medium Sea Green': '#3CB371',
    'Sea Green': '#2E8B57',
    'Forest Green': '#228B22',
    'Green': '#008000',
    'Dark Green': '#006400',
    'Yellow Green': '#9ACD32',
    'Olive Drab': '#6B8E23',
    'Olive': '#808000',
    'Dark Olive Green': '#556B2F',
    'Medium Aquamarine': '#66CDAA',
    'Dark Sea Green': '#8FBC8F',
    'Light Sea Green': '#20B2AA',
    'Dark Cyan': '#008B8B',
    'Teal': '#008080',
    'Dark Slate Gray': '#2F4F4F',
    'Dark Slate Grey': '#2F4F4F',
    'Medium Turquoise': '#48D1CC',
    'Light Sea Green': '#20B2AA',
    'Pale Turquoise': '#AFEEEE',
    'Aquamarine': '#7FFFD4',
    'Powder Blue': '#B0E0E6',
    'Light Blue': '#ADD8E6',
    'Sky Blue': '#87CEEB',
    'Light Sky Blue': '#87CEFA',
    'Steel Blue': '#4682B4',
    'Light Steel Blue': '#B0C4DE',
    'Light Gray': '#D3D3D3',
    'Light Grey': '#D3D3D3',
    'Gainsboro': '#DCDCDC',
    'White Smoke': '#F5F5F5',
    'White': '#FFFFFF',
    'Snow': '#FFFAFA',
    'Honeydew': '#F0FFF0',
    'Mint Cream': '#F5FFFA',
    'Azure': '#F0FFFF',
    'Alice Blue': '#F0F8FF',
    'Ghost White': '#F8F8FF',
    'Seashell': '#FFF5EE',
    'Beige': '#F5F5DC',
    'Old Lace': '#FDF5E6',
    'Floral White': '#FFFAF0',
    'Ivory': '#FFFFF0',
    'Antique White': '#FAEBD7',
    'Linen': '#FAF0E6',
    'Lavender Blush': '#FFF0F5',
    'Misty Rose': '#FFE4E1',
    'Black': '#000000'
};

// Reverse lookup for hex to name
const hexToName = {};
Object.entries(colorDatabase).forEach(([name, hex]) => {
    hexToName[hex.toLowerCase()] = name;
});

document.addEventListener('DOMContentLoaded', function () {
    const nameInput = document.getElementById('{{ form.name.id_for_label }}');
    const hexInput = document.getElementById('{{ form.hex_code.id_for_label }}');
    const nameSuggestions = document.getElementById('nameSuggestions');
    const hexSuggestions = document.getElementById('hexSuggestions');
    const colorSwatch = document.getElementById('colorSwatch');
    const previewColorName = document.getElementById('previewColorName');
    const previewColorHex = document.getElementById('previewColorHex');

    let selectedIndex = -1;

    // Update color preview
    function updateColorPreview() {
        const name = nameInput.value.trim();
        const hex = hexInput.value.trim();

        let displayName = 'No color selected';
        let displayHex = '#FFFFFF';
        let backgroundColor = '#FFFFFF';

        if (hex && hex.match(/^#[0-9A-Fa-f]{6}$/)) {
            displayHex = hex.toUpperCase();
            backgroundColor = hex;
            if (hexToName[hex.toLowerCase()]) {
                displayName = hexToName[hex.toLowerCase()];
            } else {
                displayName = 'Custom Color';
            }
        } else if (name && colorDatabase[name]) {
            displayHex = colorDatabase[name];
            backgroundColor = colorDatabase[name];
            displayName = name;
        }

        colorSwatch.style.backgroundColor = backgroundColor;
        previewColorName.textContent = displayName;
        previewColorHex.textContent = displayHex;
    }

    // Show suggestions for name input
    function showNameSuggestions(query) {
        const suggestions = Object.keys(colorDatabase).filter(name => name.toLowerCase().includes(query.toLowerCase())).slice(0, 10);

        nameSuggestions.innerHTML = '';

        if (suggestions.length > 0) {
            suggestions.forEach((name, index) => {
                const item = document.createElement('div');
                item.className = 'suggestion-item';
                item.innerHTML = `
                <div class="suggestion-color" style="background-color: ${
                    colorDatabase[name]
                }"></div>
                <div class="suggestion-text">
                  <div class="suggestion-name">${name}</div>
                  <div class="suggestion-hex">${
                    colorDatabase[name]
                }</div>
                </div>
              `;
                item.addEventListener('click', () => {
                    nameInput.value = name;
                    hexInput.value = colorDatabase[name];
                    nameSuggestions.style.display = 'none';
                    updateColorPreview();
                });
                nameSuggestions.appendChild(item);
            });
            nameSuggestions.style.display = 'block';
        } else {
            nameSuggestions.style.display = 'none';
        }
    }

    // Show suggestions for hex input
    function showHexSuggestions(query) {
        const suggestions = Object.entries(colorDatabase).filter(([name, hex]) => hex.toLowerCase().includes(query.toLowerCase())).slice(0, 10);

        hexSuggestions.innerHTML = '';

        if (suggestions.length > 0) {
            suggestions.forEach(([
                name, hex
            ], index) => {
                const item = document.createElement('div');
                item.className = 'suggestion-item';
                item.innerHTML = `
                <div class="suggestion-color" style="background-color: ${hex}"></div>
                <div class="suggestion-text">
                  <div class="suggestion-name">${name}</div>
                  <div class="suggestion-hex">${hex}</div>
                </div>
              `;
                item.addEventListener('click', () => {
                    hexInput.value = hex;
                    nameInput.value = name;
                    hexSuggestions.style.display = 'none';
                    updateColorPreview();
                });
                hexSuggestions.appendChild(item);
            });
            hexSuggestions.style.display = 'block';
        } else {
            hexSuggestions.style.display = 'none';
        }
    }

    // Event listeners for name input
    nameInput.addEventListener('input', function () {
        const query = this.value.trim();
        if (query.length > 0) {
            showNameSuggestions(query);
        } else {
            nameSuggestions.style.display = 'none';
        } updateColorPreview();
    });

    nameInput.addEventListener('focus', function () {
        const query = this.value.trim();
        if (query.length > 0) {
            showNameSuggestions(query);
        }
    });

    // Event listeners for hex input
    hexInput.addEventListener('input', function () {
        const query = this.value.trim();
        if (query.length > 0) {
            showHexSuggestions(query);
        } else {
            hexSuggestions.style.display = 'none';
        } updateColorPreview();
    });

    hexInput.addEventListener('focus', function () {
        const query = this.value.trim();
        if (query.length > 0) {
            showHexSuggestions(query);
        }
    });

    // Hide suggestions when clicking outside
    document.addEventListener('click', function (e) {
        if (! nameInput.contains(e.target) && ! nameSuggestions.contains(e.target)) {
            nameSuggestions.style.display = 'none';
        }
        if (! hexInput.contains(e.target) && ! hexSuggestions.contains(e.target)) {
            hexSuggestions.style.display = 'none';
        }
    });

    // Initialize color preview
    updateColorPreview();

    // Set initial values if editing
    {% if color %}nameInput.value = '{{ color.name }}';
        hexInput.value = '{{ color.hex_code|default:"" }}';
        updateColorPreview();{% endif %}
});
