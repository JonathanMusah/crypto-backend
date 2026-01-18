"""
Utility functions for image processing, watermarking, and duplicate detection
"""
import hashlib
import logging
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

logger = logging.getLogger(__name__)


def add_watermark(image_file, watermark_text=None, opacity=0.3):
    """
    Add a watermark to an image
    
    Args:
        image_file: File-like object or PIL Image
        watermark_text: Text to use as watermark (default: platform name)
        opacity: Opacity of watermark (0.0 to 1.0)
    
    Returns:
        PIL Image with watermark
    """
    try:
        # Open image
        if isinstance(image_file, Image.Image):
            img = image_file.copy()
        else:
            image_file.seek(0)
            img = Image.open(image_file)
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Create watermark text
        if watermark_text is None:
            watermark_text = "CryptoBuySell.com"
        
        # Create a transparent overlay
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Try to use a nice font, fallback to default
        try:
            # Try to use a system font
            font_size = max(img.width, img.height) // 20
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
                except:
                    font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Calculate text position (center)
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (img.width - text_width) // 2
        y = (img.height - text_height) // 2
        
        # Draw watermark with opacity
        alpha = int(255 * opacity)
        draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)
        
        # Composite watermark onto image
        watermarked = Image.alpha_composite(img.convert('RGBA'), overlay)
        watermarked = watermarked.convert('RGB')
        
        return watermarked
    
    except Exception as e:
        logger.error(f"Error adding watermark: {str(e)}")
        # Return original image if watermarking fails
        if isinstance(image_file, Image.Image):
            return image_file.copy()
        image_file.seek(0)
        return Image.open(image_file)


def compute_image_hash(image_file):
    """
    Compute perceptual hash for duplicate detection
    
    Args:
        image_file: File-like object or PIL Image
    
    Returns:
        str: Hex hash string
    """
    try:
        import imagehash
        
        if isinstance(image_file, Image.Image):
            img = image_file
        else:
            image_file.seek(0)
            img = Image.open(image_file)
        
        hash_value = imagehash.phash(img)
        return str(hash_value)
    
    except ImportError:
        logger.warning("imagehash not available, using MD5 fallback")
        # Fallback to MD5 if imagehash not available
        if isinstance(image_file, Image.Image):
            buffer = BytesIO()
            image_file.save(buffer, format='PNG')
            buffer.seek(0)
            image_file = buffer
        else:
            image_file.seek(0)
        
        return hashlib.md5(image_file.read()).hexdigest()
    
    except Exception as e:
        logger.error(f"Error computing image hash: {str(e)}")
        return None


def check_image_duplicate(image_file, existing_hashes, threshold=85):
    """
    Check if an image is a duplicate of existing images
    
    Args:
        image_file: File-like object or PIL Image
        existing_hashes: List of existing hash strings
        threshold: Similarity threshold (0-100)
    
    Returns:
        bool: True if duplicate found
    """
    try:
        import imagehash
        
        current_hash = compute_image_hash(image_file)
        if not current_hash:
            return False
        
        current_hash_obj = imagehash.hex_to_hash(current_hash)
        
        for existing_hash in existing_hashes:
            if not existing_hash:
                continue
            try:
                existing_hash_obj = imagehash.hex_to_hash(existing_hash)
                distance = current_hash_obj - existing_hash_obj
                similarity = ((64 - distance) / 64) * 100
                
                if similarity > threshold:
                    return True
            except Exception:
                continue
        
        return False
    
    except ImportError:
        # If imagehash not available, use MD5 exact match
        current_hash = compute_image_hash(image_file)
        return current_hash in existing_hashes if current_hash else False
    
    except Exception as e:
        logger.error(f"Error checking image duplicate: {str(e)}")
        return False


def process_uploaded_image(image_file, add_watermark_flag=True, watermark_text=None):
    """
    Process an uploaded image: add watermark and return processed image
    
    Args:
        image_file: Django UploadedFile or file-like object
        add_watermark_flag: Whether to add watermark
        watermark_text: Custom watermark text
    
    Returns:
        InMemoryUploadedFile: Processed image file
    """
    try:
        # Open and process image
        image_file.seek(0)
        img = Image.open(image_file)
        
        # Add watermark if requested
        if add_watermark_flag:
            img = add_watermark(img, watermark_text)
        
        # Convert to bytes
        output = BytesIO()
        img.save(output, format='PNG', quality=95)
        output.seek(0)
        
        # Create InMemoryUploadedFile
        processed_file = InMemoryUploadedFile(
            output,
            'ImageField',
            image_file.name,
            'image/png',
            sys.getsizeof(output),
            None
        )
        
        return processed_file
    
    except Exception as e:
        logger.error(f"Error processing uploaded image: {str(e)}")
        # Return original file if processing fails
        image_file.seek(0)
        return image_file

