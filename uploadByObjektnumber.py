import os
from datetime import datetime
from dotenv import load_dotenv
from services.imagegrid import ImageGridService
from services.uploadtracker import ImageUploadTracker
from services.findnearast import FindNearestService
from services.arcgis import ArcGISService
from services.image_processing import ImageProcessingService

# Load environment variables from .env file
load_dotenv()

class ToppbefaringUploader:
    def __init__(self, client_id=None, client_secret=None, token_url=None, imgr_api_url=None, tracking_file=None):
        # Use environment variables if not provided
        self.client_id = client_id or os.getenv('IMAGEGRID_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('IMAGEGRID_CLIENT_SECRET')
        self.token_url = token_url or os.getenv('IMAGEGRID_TOKEN_URL')
        self.imgr_api_url = imgr_api_url or os.getenv('IMAGEGRID_API_URL')
        self.kilde = os.getenv('KILDE', 'test toppbefaring 2025')
        self.tracking_file = self.kilde.replace(" ", "_").lower() + "_upload_log.csv"

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
        upload_result = None
        try:
            # Handle resizing if requested
            upload_path = image_path
            max_width = 7680 
            max_height = 4320
            quality = 90
            
            # Calculate file hash (use original path for tracking)
            file_hash = self.image_service.calculate_file_hash(image_path, 'md5')

            # Check if already uploaded
            is_uploaded, upload_time, update_time = self.tracker.has_been_uploaded(file_hash)
            if is_uploaded:
                print(f"Image {os.path.basename(image_path)} already uploaded at {upload_time}")
                return None
            
            print(f"Checking if image {os.path.basename(image_path)} exists in ImageGrid...")
            exist_in_imagegrid = self.image_service.check_image_exists(file_hash)
            print(f"Exist in ImageGrid: {exist_in_imagegrid}")

            
            
            filename = os.path.basename(image_path)  # '2195163-002.jpg'
            number = filename.split('-')[0]        # '2195163'
            print(number)
            # Get GPS coordinates from image (use upload path for EXIF data)
            latitude, longitude = self.find_nearest.get_gps_from_image(image_path)

            attributes = self.arcgis_service.get_mast_by_id(number)
            mast_attributes = {}
            if( attributes is None):

                # Find nearest mast if coordinates available and find_mast is True
                if find_mast and latitude and longitude:
                    nearest_mast = self.arcgis_service.find_nearest_mast(latitude, longitude)
                    if nearest_mast:
                        mast_attributes = self.arcgis_service.get_mast_attributes(nearest_mast)
                        print(f"Found nearest mast: {mast_attributes.get('driftsmerking', 'Unknown')} at {nearest_mast.get('distance', 0):.2f}m")
                    else:
                        print(f"No nearby mast found for {os.path.basename(image_path)}")
                        log_data = [
                            os.path.basename(image_path),
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            file_hash,
                            upload_time if upload_time else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            update_time if update_time else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "No nearby mast found"
                        ]
                        self.tracker.log_upload(log_data)
                        return None
            else:
                mast_attributes = self.arcgis_service.get_mast_attributes(attributes)

            if exist_in_imagegrid:
                print(f"Image {os.path.basename(image_path)} already exists in ImageGrid.")
                # Log the upload in tracking file to avoid future re-uploads
                image_id = exist_in_imagegrid.get('id')
                status = "updated_image" if image_id else "exists_no_id"
                #return None

            else:
                upload_path = self.image_processor.resize_image_with_exif(
                    image_path, max_width, max_height, quality
                )
                # Upload the image
                upload_result = self.image_service.upload_image(upload_path, file_hash)

                print(f"Upload result: {upload_result}")

                if not upload_result:
                    print(f"Failed to upload {image_path}")
                    upload_result = None
                    # continue to finally block for logging
                    return None

                # Delete the resized file if it was created
                try:
                    if upload_path != image_path and os.path.exists(upload_path):
                        os.remove(upload_path)
                except Exception as e:
                    print(f"Warning: Could not delete temporary file {upload_path}: {str(e)}")

                image_id = upload_result.get('id') if upload_result else None

                status = "new_image"

            print(f"Uploaded image ID: {image_id}")
            #image_id = '04ea4093-eac9-4330-b102-423549138bbb'
            if not image_id:
                print(f"No ID returned for {image_path}")
                return None

            # Combine base attributes with mast attributes
            combined_attributes = base_attributes.copy()
            combined_attributes.update(mast_attributes)

            #print(f"mast_attributes attributes: {mast_attributes}")
            # Add GPS coordinates if available
            if latitude and longitude:
                longitude, latitude = self.arcgis_service.transform_utm_to_gps(mast_attributes.get('geometry', {}).get('x', longitude), mast_attributes.get('geometry', {}).get('y', latitude))

            """ print(f"Combined attributes for {os.path.basename(image_path)}: {combined_attributes}") """

            objectnumber = mast_attributes.get('id', '')
            driftsmerking = combined_attributes.get('driftsmerking', '')
            linje_navn = combined_attributes.get('linje_navn', '')
            linje_id = combined_attributes.get('linje_nummer', '')
            filename = combined_attributes.get('Name', '')

            longitude, latitude = self.arcgis_service.transform_utm_to_gps(mast_attributes.get('geometry', {}).get('x', longitude), mast_attributes.get('geometry', {}).get('y', latitude))
            
            imageinfo = {
                    'filename': filename,
                    "Location": {"type": "Point", "coordinates": [latitude, longitude]} if latitude and longitude else None,
                    'objektnummer': objectnumber,
                    'linje_navn': linje_navn,
                    'linje_id': linje_id,
                    'driftsmerking': driftsmerking,
                    'erHistorisk': False,
                    'kilde': self.kilde,
                    'anleggstype': "MS",
                    'filehash': file_hash
                }
            # Update image info with toppbefaring attributes
            update_result = self.image_service.update_image_info(image_id, imageinfo, self.tenant_name, self.schema_name)
            #print(f"Update result: {update_result}")
            if update_result == "Update failed":
                print(f"Failed to update attributes for {image_path}")
                return None

            # Log the upload with all fields from imageinfo
            log_data = [
                imageinfo.get('filename', ''),
                imageinfo.get('Location', ''),
                imageinfo.get('objektnummer', ''),
                imageinfo.get('linje_navn', ''),
                imageinfo.get('linje_id', ''),
                imageinfo.get('driftsmerking', ''),
                imageinfo.get('erHistorisk', ''),
                imageinfo.get('kilde', ''),
                imageinfo.get('anleggstype', ''),
                imageinfo.get('filehash', ''),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status if exist_in_imagegrid else "ok"
            ]

            """ print(f"Logging upload: {log_data}") """
            self.tracker.log_upload(log_data)

            print(f"Successfully uploaded and updated {imageinfo.get('filename')}")
            return upload_result

        except Exception as e:
            print(f"Error uploading {image_path}: {str(e)}")
            # Log failed upload attempt
            try:
                filename = os.path.basename(image_path)
                file_hash = self.image_service.calculate_file_hash(image_path, 'md5') if hasattr(self, 'image_service') else 'unknown'
                # Lag failed_data med samme rekkefølge og antall kolonner som log_data/imageinfo
                failed_data = [
                    filename,                # filename
                    None,                    # Location
                    None,                    # objektnummer
                    None,                    # linje_navn
                    None,                    # linje_id
                    None,                    # driftsmerking
                    None,                    # erHistorisk
                    None,                    # kilde
                    None,                    # anleggstype
                    file_hash,               # filehash
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # uploadtime
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # updatetime
                    "failed"                # status
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

# Example usage
if __name__ == "__main__":
    try:
        # Create uploader with credentials from environment variables
        uploader = ToppbefaringUploader()

        # Example attributes template based on the provided model
        attributes_template = {
            "Model": "",
            "kilde": "",
            "DateTime": "",
            "FileRole": "",
            "SourceId": "",
            "linje_id": "",
            "linje_navn": "",
            "Orientation": 1,
            "anleggstype": "",
            "erhistorisk": "",
            "objektnummer": "",
            "arcgis_synced": False,
            "driftsmerking": "",
            "SchemaTemplate": "Toppbefaring"
        }

        # Get upload folder path from environment or use default
        folder_path = os.getenv('UPLOAD_FOLDER_PATH', r"C:\devop\imagegridbilder\toppbefaring2025")


        uploader.upload_from_folder(folder_path, attributes_template, find_mast=True, resize_options='high_quality')

        
    except Exception as main_e:
        print(f"Error in main execution: {str(main_e)}")