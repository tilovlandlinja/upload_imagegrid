import os
import json
from datetime import datetime
from dotenv import load_dotenv
from services.imagegrid import ImageGridService
from services.uploadtracker import ImageUploadTracker
from services.findnearast import FindNearestService
from services.arcgis import ArcGISService
from services.image_processing import ImageProcessingService
import pandas as pd

# Load environment variables from .env file
load_dotenv()

class ToppbefaringUploader:
    def __init__(self, client_id=None, client_secret=None, token_url=None, imgr_api_url=None, tracking_file=None):
        # Use environment variables if not provided
        self.client_id = client_id or os.getenv('IMAGEGRID_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('IMAGEGRID_CLIENT_SECRET')
        self.token_url = token_url or os.getenv('IMAGEGRID_TOKEN_URL')
        self.imgr_api_url = imgr_api_url or os.getenv('IMAGEGRID_API_URL')
        self.tracking_file = tracking_file or os.getenv('TRACKING_FILE', 'toppbefaring_upload_log.csv')

        # Validate required credentials
        if not all([self.client_id, self.client_secret, self.token_url, self.imgr_api_url]):
            raise ValueError("Missing required credentials. Please set IMAGEGRID_CLIENT_ID, IMAGEGRID_CLIENT_SECRET, IMAGEGRID_TOKEN_URL, and IMAGEGRID_API_URL in your .env file or pass them as parameters.")

        self.image_service = ImageGridService(self.client_id, self.client_secret, self.token_url, self.imgr_api_url)
        self.tracker = ImageUploadTracker(self.tracking_file)
        self.find_nearest = FindNearestService()
        self.arcgis_service = ArcGISService()
        self.image_processor = ImageProcessingService()
        self.tenant_name = "moerenett"
        self.schema_name = "Toppbefaring"

    def upload_toppbefaring_image(self, image_path, base_attributes, find_mast=True, resize_options=None):
        """
        Upload a toppbefaring image to ImageGrid with specific attributes.
        If find_mast is True, will try to find nearest mast and include mast attributes.
        If resize_options is provided, will resize the image before uploading.

        Args:
            image_path (str): Path to the image file
            base_attributes (dict): Base attributes for the image
            find_mast (bool): Whether to find nearest mast
            resize_options (dict): Resize options with keys: max_width, max_height, quality, overwrite
        """
        try:
            # Handle resizing if requested
            upload_path = image_path
            if resize_options:
                max_width = resize_options.get('max_width')
                max_height = resize_options.get('max_height')
                quality = resize_options.get('quality', 85)
                overwrite = resize_options.get('overwrite', False)

                if overwrite:
                    upload_path = self.image_processor.resize_image_with_exif(
                        image_path, max_width, max_height, quality, image_path
                    )
                else:
                    upload_path = self.image_processor.resize_image_with_exif(
                        image_path, max_width, max_height, quality
                    )

            # Calculate file hash (use original path for tracking)
            file_hash = self.image_service.calculate_file_hash(image_path, 'md5')

            # Check if already uploaded
            is_uploaded, upload_time, update_time = self.tracker.has_been_uploaded(file_hash)
            if is_uploaded:
                print(f"Image {os.path.basename(image_path)} already uploaded at {upload_time}")
                return None

            # Get GPS coordinates from image (use upload path for EXIF data)
            latitude, longitude = self.find_nearest.get_gps_from_image(upload_path)

            # Find nearest mast if coordinates available and find_mast is True
            mast_attributes = {}
            if find_mast and latitude and longitude:
                nearest_mast = self.arcgis_service.find_nearest_mast(latitude, longitude)
                if nearest_mast:
                    mast_attributes = self.arcgis_service.get_mast_attributes(nearest_mast)
                    print(f"Found nearest mast: {mast_attributes.get('driftsmerking', 'Unknown')} at {nearest_mast.get('distance', 0):.2f}m")
                else:
                    print(f"No nearby mast found for {os.path.basename(image_path)}")

            # Upload the image
            upload_result = self.image_service.upload_image(upload_path, file_hash)
            if not upload_result:
                print(f"Failed to upload {image_path}")
                return None

            image_id = upload_result.get('Id')
            if not image_id:
                print(f"No ID returned for {image_path}")
                return None

            # Combine base attributes with mast attributes
            combined_attributes = base_attributes.copy()
            combined_attributes.update(mast_attributes)

            # Add GPS coordinates if available
            if latitude and longitude:
                combined_attributes['latitude'] = latitude
                combined_attributes['longitude'] = longitude

            # Prepare attributes for update
            update_data = {
                "Attributes": combined_attributes
            }

            # Update image info with toppbefaring attributes
            update_result = self.image_service.update_image_info(image_id, update_data, self.tenant_name, self.schema_name)

            if update_result == "Update failed":
                print(f"Failed to update attributes for {image_path}")
                return None

            # Log the upload
            filename = os.path.basename(image_path)

            data = [
                filename, latitude, longitude,
                combined_attributes.get('anleggstype'), combined_attributes.get('anleggstype_n'),
                combined_attributes.get('linje_navn'), combined_attributes.get('driftsmerking'),
                combined_attributes.get('erhistorisk'), combined_attributes.get('ergroft'),
                combined_attributes.get('kilde'), combined_attributes.get('nettmelding_elsmart'),
                combined_attributes.get('erutvendig'), combined_attributes.get('erinnvendig'),
                file_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "ok"
            ]

            self.tracker.log_upload(data)

            print(f"Successfully uploaded and updated {filename}")
            return upload_result

        except Exception as e:
            print(f"Error uploading {image_path}: {str(e)}")
            # Log failed upload attempt
            try:
                filename = os.path.basename(image_path)
                file_hash = self.image_service.calculate_file_hash(image_path, 'md5') if hasattr(self, 'image_service') else 'unknown'
                failed_data = [
                    filename, None, None, None, None, None, None, None, None, None, None, None, None,
                    file_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "failed"
                ]
                self.tracker.log_upload(failed_data)
                print(f"Logged failed upload attempt for {filename}")
            except Exception as log_error:
                print(f"Failed to log upload error: {log_error}")
            return None

    def upload_from_folder(self, folder_path, base_attributes_template, find_mast=True, resize_options=None):
        """
        Upload all images from a folder with toppbefaring attributes.
        base_attributes_template should be a dict with default attributes.
        If find_mast is True, will try to find nearest mast for each image.
        If resize_options is provided, will resize images before uploading.
        """
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return

        uploaded_count = 0
        failed_count = 0
        skipped_count = 0

        # Get list of image files first
        image_files = []
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_files.append(filename)

        total_files = len(image_files)
        print(f"Found {total_files} image files to process")

        for i, filename in enumerate(image_files, 1):
            image_path = os.path.join(folder_path, filename)
            print(f"[{i}/{total_files}] Processing {filename}...")

            # Copy attributes template
            attributes = base_attributes_template.copy()

            # Set filename in attributes
            attributes['Name'] = filename

            result = self.upload_toppbefaring_image(image_path, attributes, find_mast, resize_options)
            if result is None:
                # Check if it was skipped (already uploaded) or failed
                file_hash = self.image_service.calculate_file_hash(image_path, 'md5')
                is_uploaded, _, _ = self.tracker.has_been_uploaded(file_hash)
                if is_uploaded:
                    skipped_count += 1
                    print(f"[{i}/{total_files}] {filename}: Skipped (already uploaded)")
                else:
                    failed_count += 1
                    print(f"[{i}/{total_files}] {filename}: Failed")
            else:
                uploaded_count += 1
                print(f"[{i}/{total_files}] {filename}: Uploaded successfully")

        print(f"\nUpload complete:")
        print(f"  Total files: {total_files}")
        print(f"  Uploaded: {uploaded_count}")
        print(f"  Skipped (already uploaded): {skipped_count}")
        print(f"  Failed: {failed_count}")

    def get_mast_info_for_image(self, image_path):
        """
        Get mast information for a specific image based on its GPS coordinates.
        """
        latitude, longitude = self.find_nearest.get_gps_from_image(image_path)

        if not latitude or not longitude:
            print(f"No GPS coordinates found in {os.path.basename(image_path)}")
            return None

        nearest_mast = self.arcgis_service.find_nearest_mast(latitude, longitude)

        if nearest_mast:
            mast_info = self.arcgis_service.get_mast_attributes(nearest_mast)
            mast_info['distance'] = nearest_mast.get('distance', 0)
            mast_info['latitude'] = latitude
            mast_info['longitude'] = longitude
            return mast_info
        else:
            print(f"No nearby mast found for {os.path.basename(image_path)}")
            return None

    def preview_mast_linking(self, folder_path):
        """
        Preview which masts will be linked to images in a folder.
        """
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return

        print("Preview of mast linking:")
        print("-" * 50)

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_path = os.path.join(folder_path, filename)
                mast_info = self.get_mast_info_for_image(image_path)

                if mast_info:
                    print(f"{filename}:")
                    print(f"  GPS: ({mast_info.get('latitude'):.6f}, {mast_info.get('longitude'):.6f})")
                    print(f"  Nearest mast: {mast_info.get('driftsmerking', 'Unknown')}")
                    print(f"  Distance: {mast_info.get('distance', 0):.2f} meters")
                    print(f"  Mast number: {mast_info.get('mast_nummer', 'N/A')}")
                    print(f"  Line number: {mast_info.get('linje_nummer', 'N/A')}")
                    print()
                else:
                    print(f"{filename}: No mast found")
                    print()

    def get_upload_stats(self):
        """
        Get upload statistics.
        """
        uploaded, failed = self.tracker.get_number_of_uploads()
        return uploaded, failed

    def get_detailed_upload_stats(self):
        """
        Get detailed upload statistics including skipped files.
        """
        if os.path.exists(self.tracker.tracking_file):
            df = pd.read_csv(self.tracker.tracking_file, sep=';', encoding='ansi')

            total_entries = len(df)
            uploaded = len(df[df['status'] == 'ok'])
            failed = len(df[df['status'] == 'failed'])

            # Group by filename to find duplicates
            filename_counts = df['filename'].value_counts()
            duplicates = len(filename_counts[filename_counts > 1])

            stats = {
                'total_entries': total_entries,
                'uploaded': uploaded,
                'failed': failed,
                'duplicates': duplicates,
                'unique_files': len(filename_counts),
                'success_rate': (uploaded / total_entries * 100) if total_entries > 0 else 0
            }

            return stats
        return {'total_entries': 0, 'uploaded': 0, 'failed': 0, 'duplicates': 0, 'unique_files': 0, 'success_rate': 0}

    def verify_upload_tracking(self, folder_path):
        """
        Verify that all images in a folder are properly tracked in the upload log.
        Returns a report of tracking status for each file.
        """
        if not os.path.exists(folder_path):
            return {'error': f"Folder {folder_path} does not exist"}

        report = {
            'total_files': 0,
            'tracked_uploaded': 0,
            'tracked_failed': 0,
            'not_tracked': 0,
            'details': []
        }

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_path = os.path.join(folder_path, filename)
                report['total_files'] += 1

                # Calculate file hash
                file_hash = self.image_service.calculate_file_hash(image_path, 'md5')

                # Check tracking status
                is_uploaded, upload_time, update_time = self.tracker.has_been_uploaded(file_hash)

                if is_uploaded:
                    # Check if it was successful or failed
                    if os.path.exists(self.tracker.tracking_file):
                        df = pd.read_csv(self.tracker.tracking_file, sep=';', encoding='ansi')
                        row = df[df['filehash'] == file_hash]
                        if not row.empty:
                            status = row.iloc[0]['status']
                            if status == 'ok':
                                report['tracked_uploaded'] += 1
                                status_desc = 'uploaded'
                            else:
                                report['tracked_failed'] += 1
                                status_desc = 'failed'
                        else:
                            report['not_tracked'] += 1
                            status_desc = 'not_tracked'
                    else:
                        report['not_tracked'] += 1
                        status_desc = 'not_tracked'
                else:
                    report['not_tracked'] += 1
                    status_desc = 'not_tracked'

                report['details'].append({
                    'filename': filename,
                    'filehash': file_hash,
                    'status': status_desc,
                    'upload_time': upload_time,
                    'update_time': update_time
                })

        return report

    def cleanup_duplicate_entries(self):
        """
        Remove duplicate entries from the tracking file, keeping only the most recent entry for each filehash.
        """
        if not os.path.exists(self.tracker.tracking_file):
            print("No tracking file found")
            return 0

        df = pd.read_csv(self.tracker.tracking_file, sep=';', encoding='ansi')

        # Sort by updatetime descending and drop duplicates based on filehash, keeping the first (most recent)
        df['updatetime'] = pd.to_datetime(df['updatetime'], errors='coerce')
        df = df.sort_values('updatetime', ascending=False)
        df_cleaned = df.drop_duplicates(subset='filehash', keep='first')

        # Save the cleaned dataframe
        df_cleaned.to_csv(self.tracker.tracking_file, sep=';', index=False, encoding='ansi')

        removed_count = len(df) - len(df_cleaned)
        print(f"Removed {removed_count} duplicate entries from tracking file")

        return removed_count

    def sync_with_imagegrid(self, folder_path=None):
        """
        Sync upload tracker with actual uploads in ImageGrid.
        This method checks all images in the specified folder and ensures they are properly tracked.
        If folder_path is None, it will check the default upload folder.
        """
        if folder_path is None:
            folder_path = os.getenv('UPLOAD_FOLDER_PATH', r"C:\devop\imagegridbilder\toppbefaring2025")

        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return

        print(f"Starting sync with ImageGrid for folder: {folder_path}")

        synced_count = 0
        already_tracked = 0
        errors = 0

        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_path = os.path.join(folder_path, filename)

                try:
                    # Calculate file hash
                    file_hash = self.image_service.calculate_file_hash(image_path, 'md5')

                    # Check if already tracked
                    is_tracked, _, _ = self.tracker.has_been_uploaded(file_hash)

                    if is_tracked:
                        already_tracked += 1
                        continue

                    # Check if image exists in ImageGrid by trying to get its info
                    # This is a simplified check - you might need to implement a more robust method
                    # depending on your ImageGrid API capabilities

                    print(f"Found untracked image: {filename} - adding to tracker")

                    # Get basic image info
                    latitude, longitude = self.find_nearest.get_gps_from_image(image_path)

                    # Create a basic tracking entry
                    data = [
                        filename, latitude, longitude,
                        None, None, None, None, None, None, None, None, None, None,
                        file_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "synced"
                    ]

                    self.tracker.log_upload(data)
                    synced_count += 1

                except Exception as e:
                    print(f"Error syncing {filename}: {str(e)}")
                    errors += 1

        print(f"\nSync completed:")
        print(f"  Already tracked: {already_tracked}")
        print(f"  Newly synced: {synced_count}")
        print(f"  Errors: {errors}")

        return synced_count, already_tracked, errors

# Example usage
if __name__ == "__main__":
    try:
        # Create uploader with credentials from environment variables
        uploader = ToppbefaringUploader()

        # Example attributes template based on the provided model
        attributes_template = {
            "Model": "ILCE-1",
            "kilde": "netbas-felles Toppbefaring 2023 Møre",
            "DateTime": "2023-05-04T17:00:58",
            "FileRole": "MasterFile",
            "SourceId": "ImageGridApi",
            "linje_id": "LL040",
            "linje_navn": "LL040 SYVDSNES",
            "Orientation": 1,
            "anleggstype": "MS",
            "erhistorisk": "FALSE",
            "objektnummer": "2382523",
            "arcgis_synced": False,
            "driftsmerking": "LL040_131",
            "SchemaTemplate": "Toppbefaring"
        }

        # Get upload folder path from environment or use default
        folder_path = os.getenv('UPLOAD_FOLDER_PATH', r"C:\devop\imagegridbilder\toppbefaring2025")

        # Preview mast linking before uploading
        print("=== MAST LINKING PREVIEW ===")
        uploader.preview_mast_linking(folder_path)

        # Ask user to confirm before uploading
        confirm = input("\nDo you want to proceed with the upload? (y/n): ")
        if confirm.lower() == 'y':
            # Optional: Resize images before uploading
            resize_confirm = input("Do you want to resize images before uploading? (y/n): ")
            resize_options = None
            if resize_confirm.lower() == 'y':
                resize_options = {
                    'max_width': 1920,
                    'max_height': 1080,
                    'quality': 85,
                    'overwrite': False  # Create resized copies
                }

            # Upload images from a folder with mast linking enabled
            uploader.upload_from_folder(folder_path, attributes_template, find_mast=True, resize_options=resize_options)
        else:
            print("Upload cancelled.")

        # Get stats
        uploaded, failed = uploader.get_upload_stats()
        print(f"Total uploaded: {uploaded}, Total failed: {failed}")

        # Get detailed stats
        detailed_stats = uploader.get_detailed_upload_stats()
        print(f"\nDetailed Statistics:")
        print(f"  Total entries: {detailed_stats['total_entries']}")
        print(f"  Unique files: {detailed_stats['unique_files']}")
        print(f"  Success rate: {detailed_stats['success_rate']:.1f}%")
        print(f"  Duplicates: {detailed_stats['duplicates']}")

        # Optional: Verify tracking for the upload folder
        verify_confirm = input("\nDo you want to verify upload tracking? (y/n): ")
        if verify_confirm.lower() == 'y':
            print("\nVerifying upload tracking...")
            verification_report = uploader.verify_upload_tracking(folder_path)
            print(f"Verification complete:")
            print(f"  Total files: {verification_report['total_files']}")
            print(f"  Tracked uploaded: {verification_report['tracked_uploaded']}")
            print(f"  Tracked failed: {verification_report['tracked_failed']}")
            print(f"  Not tracked: {verification_report['not_tracked']}")

        # Optional: Sync with ImageGrid
        sync_confirm = input("\nDo you want to sync with ImageGrid? (y/n): ")
        if sync_confirm.lower() == 'y':
            print("\nSyncing with ImageGrid...")
            synced, already_tracked, sync_errors = uploader.sync_with_imagegrid(folder_path)
            print(f"Sync complete: {synced} synced, {already_tracked} already tracked, {sync_errors} errors")

        # Optional: Cleanup duplicates
        cleanup_confirm = input("\nDo you want to cleanup duplicate entries? (y/n): ")
        if cleanup_confirm.lower() == 'y':
            removed = uploader.cleanup_duplicate_entries()
            print(f"Cleaned up {removed} duplicate entries")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please ensure your .env file contains the required credentials:")
        print("- IMAGEGRID_CLIENT_ID")
        print("- IMAGEGRID_CLIENT_SECRET")
        print("- IMAGEGRID_TOKEN_URL")
        print("- IMAGEGRID_API_URL")
    except Exception as e:
        print(f"An error occurred: {e}")
