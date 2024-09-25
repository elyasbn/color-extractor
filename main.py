from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import os
from sklearn.cluster import KMeans
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from io import BytesIO

# Function to extract dominant colors from an image
def extract_palette(image_path, num_colors=5):
    image = Image.open(image_path)
    # image = image.resize((100, 100))  # Resize to speed up processing
    pixels = np.array(image).reshape(-1, 3)  # Flatten the image into RGB pixels

    kmeans = KMeans(n_clusters=num_colors).fit(pixels)
    palette = kmeans.cluster_centers_.astype(int)
    return palette

# Function to convert RGB to Hex
def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def create_glassy_background(width, height, fill_color=(255, 255, 255, 64)):
    background = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(background)
    draw.rounded_rectangle([(0, 0), (width, height)], radius=15, fill=fill_color)
    return background.filter(ImageFilter.GaussianBlur(radius=5))

def save_palette(palette, file_obj, background_image_path):
    # Open the uploaded image to use as the background
    background_image = Image.open(background_image_path)
    
    # Resize the background image to have a width of 1000px (maintaining aspect ratio)
    base_width = 1000
    w_percent = base_width / float(background_image.size[0])
    h_size = int(float(background_image.size[1]) * float(w_percent))
    background_image = background_image.resize((base_width, h_size), Image.LANCZOS)
    
    # Apply a blur effect to the background
    background_image = background_image.filter(ImageFilter.GaussianBlur(radius=10))
    
    # Darken the background
    darkened_background = Image.new('RGBA', background_image.size, (0, 0, 0, 128))
    background_image = Image.alpha_composite(background_image.convert('RGBA'), darkened_background)
    
    image_width, image_height = background_image.size
    
    # Create a glassy background for the palette box
    palette_box_height = 180  # Increased height to accommodate larger text
    palette_box_width = min(650, image_width - 40)  # Max width of 650px or image width - 40px margin
    glassy_background = create_glassy_background(palette_box_width, palette_box_height)
    
    # Position the palette box at the bottom with some margin
    box_position = ((image_width - palette_box_width) // 2, image_height - palette_box_height - 30)
    background_image.paste(glassy_background, box_position, glassy_background)
    
    draw = ImageDraw.Draw(background_image)
    
    # Calculate dimensions for color circles
    circle_margin = 40
    circle_radius = 25
    total_circle_width = palette_box_width - (2 * circle_margin)
    spacing = total_circle_width // (len(palette) - 1)
    
    # Draw circles for each color in the palette
    for i, color in enumerate(palette):
        circle_x = box_position[0] + circle_margin + i * spacing
        circle_y = box_position[1] + (palette_box_height // 2) - 30  # Moved up to make room for larger text
        
        # Draw a larger white circle as background
        draw.ellipse(
            [(circle_x - circle_radius - 3, circle_y - circle_radius - 3), 
             (circle_x + circle_radius + 3, circle_y + circle_radius + 3)], 
            fill=(255, 255, 255, 200)
        )
        
        # Draw the color circle
        draw.ellipse(
            [(circle_x - circle_radius, circle_y - circle_radius), 
             (circle_x + circle_radius, circle_y + circle_radius)], 
            fill=tuple(color) + (255,)  # Add alpha channel for full opacity
        )
    
    # Add a stylish title with larger, bold text
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except IOError:
        title_font = ImageFont.load_default().font_variant(size=48)
    
    title = "Color Palette"
    title_width = draw.textlength(title, font=title_font)
    draw.text(((image_width - title_width) / 2, 20), title, font=title_font, fill=(255, 255, 255))
    
    # Add hex codes below the circles with larger, bold text
    try:
        hex_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except IOError:
        hex_font = ImageFont.load_default().font_variant(size=20)
    
    for i, color in enumerate(palette):
        hex_code = rgb_to_hex(color)
        hex_width = draw.textlength(hex_code, font=hex_font)
        circle_x = box_position[0] + circle_margin + i * spacing
        draw.text((circle_x - hex_width / 2, box_position[1] + palette_box_height - 50), 
                  hex_code, font=hex_font, fill=(255, 255, 255))
    
    # Save the final image to the provided file-like object
    background_image.save(file_obj, format='PNG')

# Async Command: Start the bot
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome to the Color Palette Bot! Upload an image to generate a color palette.")

# Async Command: Help
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text("To use this bot:\n1. Upload an image.\n2. Get a color palette based on the image.")

# Async Handler: Handling image uploads
def create_color_caption(palette):
    caption = "Color Palette:\n"
    for i, color in enumerate(palette, 1):
        hex_code = rgb_to_hex(color)
        rgb_values = f"RGB({color[0]}, {color[1]}, {color[2]})"
        caption += f"{i}. {hex_code} - {rgb_values}\n"
    return caption

# Async Handler: Handling image uploads
async def handle_image(update: Update, context: CallbackContext):
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    file_path = f"{user.id}_image.jpg"
    
    # Download the image to local storage
    await photo_file.download_to_drive(file_path)
    
    # Extract the palette from the uploaded image
    palette = extract_palette(file_path, 5)
    
    # Create the caption with color codes
    caption = create_color_caption(palette)
    
    # Save the palette image to an in-memory BytesIO object with the uploaded image as background
    with BytesIO() as image_binary:
        save_palette(palette, image_binary, file_path)  # Pass the uploaded image as background
        image_binary.seek(0)  # Move the cursor to the beginning of the BytesIO object
        
        # Send the photo with the color code caption
        await update.message.reply_photo(photo=image_binary, caption=caption)
    
    # Clean up the downloaded image
    os.remove(file_path)

# Main function to run the bot
def main():
    # Replace 'YOUR TOKEN' with the token you received from BotFather
    application = Application.builder().token("7792971926:AAGtvnw9F2FOBr1CprjOewkWlRhlm-My_eM").build()

    # Register commands and handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
