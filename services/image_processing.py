import os
from PIL import Image
import piexif

class ImageProcessingService:
    def __init__(self):
        pass

    def resize_image_with_exif(self, image_path, max_width=None, max_height=None, quality=85, output_path=None):
        """
        Resize an image while preserving all EXIF data including GPS coordinates.

        Args:
            image_path (str): Path to the input image
            max_width (int): Maximum width in pixels (optional)
            max_height (int): Maximum height in pixels (optional)
            quality (int): JPEG quality (1-100, default 85)
            output_path (str): Path for the resized image (optional, defaults to overwriting original)

        Returns:
            str: Path to the resized image
        """
        try:
            # Open the image
            with Image.open(image_path) as img:
                # Get original dimensions
                original_width, original_height = img.size

                # If no dimensions specified, return original path
                if max_width is None and max_height is None:
                    return image_path

                # Calculate new dimensions while maintaining aspect ratio
                if max_width and max_height:
                    # Calculate ratios for both dimensions
                    width_ratio = max_width / original_width
                    height_ratio = max_height / original_height
                    ratio = min(width_ratio, height_ratio)

                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)
                elif max_width:
                    ratio = max_width / original_width
                    new_width = max_width
                    new_height = int(original_height * ratio)
                elif max_height:
                    ratio = max_height / original_height
                    new_width = int(original_width * ratio)
                    new_height = max_height

                # Only resize if image is actually larger than target dimensions
                if new_width >= original_width and new_height >= original_height:
                    print(f"Image {os.path.basename(image_path)} is already smaller than target size")
                    return image_path

                # Load EXIF data
                exif_data = piexif.load(img.info.get('exif', b''))

                # Resize the image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Determine output path
                if output_path is None:
                    # Create a temporary resized version
                    base_name = os.path.splitext(os.path.basename(image_path))[0]
                    dir_name = os.path.dirname(image_path)
                    output_path = os.path.join(dir_name, f"{base_name}_resized.jpg")

                # Save with EXIF data preserved
                if exif_data:
                    # Convert EXIF data back to bytes
                    exif_bytes = piexif.dump(exif_data)
                    resized_img.save(output_path, 'JPEG', quality=quality, exif=exif_bytes)
                else:
                    resized_img.save(output_path, 'JPEG', quality=quality)

                print(f"Resized {os.path.basename(image_path)} from {original_width}x{original_height} to {new_width}x{new_height}")
                return output_path

        except Exception as e:
            print(f"Error resizing image {image_path}: {str(e)}")
            return image_path  # Return original path if resize fails

    def resize_images_in_folder(self, folder_path, max_width=None, max_height=None, quality=85, overwrite=False):
        """
        Resize all images in a folder while preserving EXIF data.

        Args:
            folder_path (str): Path to the folder containing images
            max_width (int): Maximum width in pixels
            max_height (int): Maximum height in pixels
            quality (int): JPEG quality (1-100)
            overwrite (bool): Whether to overwrite original files or create resized versions

        Returns:
            tuple: (resized_count, skipped_count)
        """
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return 0, 0

        resized_count = 0
        skipped_count = 0

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_path = os.path.join(folder_path, filename)

                if overwrite:
                    output_path = image_path
                else:
                    output_path = None  # Will create _resized version

                result_path = self.resize_image_with_exif(
                    image_path, max_width, max_height, quality, output_path
                )

                if result_path != image_path:
                    resized_count += 1
                else:
                    skipped_count += 1

        print(f"Resize complete. Resized: {resized_count}, Skipped: {skipped_count}")
        return resized_count, skipped_count

    def get_image_info(self, image_path):
        """
        Get basic information about an image.

        Args:
            image_path (str): Path to the image

        Returns:
            dict: Image information including dimensions, format, EXIF data presence
        """
        try:
            with Image.open(image_path) as img:
                info = {
                    'width': img.size[0],
                    'height': img.size[1],
                    'format': img.format,
                    'mode': img.mode,
                    'has_exif': bool(img.info.get('exif')),
                    'file_size': os.path.getsize(image_path) if os.path.exists(image_path) else 0
                }
                return info
        except Exception as e:
            print(f"Error getting image info for {image_path}: {str(e)}")
            return None

    def batch_resize_with_progress(self, folder_path, max_width=None, max_height=None, quality=85, overwrite=False):
        """
        Resize images in a folder with progress reporting.

        Args:
            folder_path (str): Path to the folder containing images
            max_width (int): Maximum width in pixels
            max_height (int): Maximum height in pixels
            quality (int): JPEG quality (1-100)
            overwrite (bool): Whether to overwrite original files or create resized versions

        Returns:
            dict: Processing results with counts and details
        """
        if not os.path.exists(folder_path):
            return {'error': f"Folder {folder_path} does not exist"}

        # Get list of image files
        image_files = []
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_files.append(filename)

        total_files = len(image_files)
        processed = 0
        resized = 0
        skipped = 0
        errors = 0

        results = {
            'total_files': total_files,
            'processed': 0,
            'resized': 0,
            'skipped': 0,
            'errors': 0,
            'details': []
        }

        print(f"Starting batch resize of {total_files} images...")

        for filename in image_files:
            image_path = os.path.join(folder_path, filename)
            processed += 1

            try:
                # Get original info
                original_info = self.get_image_info(image_path)

                if overwrite:
                    output_path = image_path
                else:
                    output_path = None

                result_path = self.resize_image_with_exif(
                    image_path, max_width, max_height, quality, output_path
                )

                # Get resized info
                resized_info = self.get_image_info(result_path) if result_path != image_path else original_info

                if result_path != image_path:
                    resized += 1
                    status = 'resized'
                else:
                    skipped += 1
                    status = 'skipped'

                results['details'].append({
                    'filename': filename,
                    'status': status,
                    'original_size': f"{original_info['width']}x{original_info['height']}" if original_info else 'unknown',
                    'resized_size': f"{resized_info['width']}x{resized_info['height']}" if resized_info else 'unknown',
                    'original_file_size': original_info['file_size'] if original_info else 0,
                    'resized_file_size': resized_info['file_size'] if resized_info else 0
                })

                print(f"[{processed}/{total_files}] {filename}: {status}")

            except Exception as e:
                errors += 1
                results['details'].append({
                    'filename': filename,
                    'status': 'error',
                    'error': str(e)
                })
                print(f"[{processed}/{total_files}] {filename}: ERROR - {str(e)}")

        results['processed'] = processed
        results['resized'] = resized
        results['skipped'] = skipped
        results['errors'] = errors

        print(f"\nBatch resize completed:")
        print(f"  Total files: {total_files}")
        print(f"  Processed: {processed}")
        print(f"  Resized: {resized}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")

        return results

    def get_resize_presets(self, original_width, original_height):
        """
        Get recommended resize presets based on original image dimensions.

        Args:
            original_width (int): Original image width
            original_height (int): Original image height

        Returns:
            dict: Dictionary of preset options with descriptions
        """
        aspect_ratio = original_width / original_height

        presets = {
            'high_quality': {
                'max_width': min(4800, original_width),
                'max_height': min(3200, original_height),
                'quality': 90,
                'description': f"High quality ({min(4800, original_width)}x{min(3200, original_height)}, 90% quality) - ~50% size, excellent zoom"
            },
            'balanced': {
                'max_width': min(3600, original_width),
                'max_height': min(2400, original_height),
                'quality': 85,
                'description': f"Balanced ({min(3600, original_width)}x{min(2400, original_height)}, 85% quality) - ~30% size, good zoom"
            },
            'compact': {
                'max_width': min(2400, original_width),
                'max_height': min(1600, original_height),
                'quality': 80,
                'description': f"Compact ({min(2400, original_width)}x{min(1600, original_height)}, 80% quality) - ~15% size, moderate zoom"
            },
            'web_optimized': {
                'max_width': 1920,
                'max_height': 1280,
                'quality': 85,
                'description': "Web optimized (1920x1280, 85% quality) - ~8% size, basic zoom"
            }
        }

        return presets

    def estimate_file_size(self, original_width, original_height, original_file_size, target_width, target_height, quality=85):
        """
        Estimate the file size after resizing.

        Args:
            original_width (int): Original image width
            original_height (int): Original image height
            original_file_size (int): Original file size in bytes
            target_width (int): Target width
            target_height (int): Target height
            quality (int): JPEG quality (1-100)

        Returns:
            dict: Estimated file size information
        """
        # Calculate pixel ratio
        pixel_ratio = (target_width * target_height) / (original_width * original_height)

        # Quality factor (rough estimation)
        quality_factor = quality / 100.0

        # Estimate new file size (this is approximate)
        estimated_size = original_file_size * pixel_ratio * quality_factor * 0.8  # 0.8 is a rough compression factor

        return {
            'estimated_size_mb': estimated_size / (1024 * 1024),
            'size_reduction_percent': (1 - pixel_ratio) * 100,
            'pixel_count_original': original_width * original_height,
            'pixel_count_target': target_width * target_height
        }

# Example usage
if __name__ == "__main__":
    processor = ImageProcessingService()

    # Resize a single image
    result_path = processor.resize_image_with_exif(
        "path/to/image.jpg",
        max_width=1920,
        max_height=1080,
        quality=85
    )
    print(f"Resized image saved to: {result_path}")

    # Resize all images in a folder
    resized, skipped = processor.resize_images_in_folder(
        "path/to/folder",
        max_width=1920,
        max_height=1080,
        overwrite=False
    )

    # Batch resize with detailed progress
    results = processor.batch_resize_with_progress(
        "path/to/folder",
        max_width=1920,
        max_height=1080,
        quality=85,
        overwrite=False
    )
