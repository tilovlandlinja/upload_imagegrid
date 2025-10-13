import os
import subprocess


import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime
from dotenv import load_dotenv
from services.imagegrid import ImageGridService
from services.uploadtracker import ImageUploadTracker
from services.findnearast import FindNearestService
from services.arcgis import ArcGISService
from services.image_processing import ImageProcessingService

# Add models directory to path if needed
models_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
if models_path not in sys.path:
    sys.path.append(models_path)

from models.image_info import ImageInfo
import pandas as pd

# Load environment variables from .env file
load_dotenv()

class DistribusjonUploader:
    def __init__(self, client_id=None, client_secret=None, token_url=None, imgr_api_url=None, tracking_file=None):
        # Use environment variables if not provided
        self.client_id = client_id or os.getenv('IMAGEGRID_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('IMAGEGRID_CLIENT_SECRET')
        self.token_url = token_url or os.getenv('IMAGEGRID_TOKEN_URL')
        self.imgr_api_url = imgr_api_url or os.getenv('IMAGEGRID_API_URL')
        self.kilde = "Nettstasjon fra hotfolder"

        # Validate required credentials
        if not all([self.client_id, self.client_secret, self.token_url, self.imgr_api_url]):
            raise ValueError("Missing required credentials. Please set IMAGEGRID_CLIENT_ID, IMAGEGRID_CLIENT_SECRET, IMAGEGRID_TOKEN_URL, and IMAGEGRID_API_URL in your .env file or pass them as parameters.")

        self.image_service = ImageGridService(self.client_id, self.client_secret, self.token_url, self.imgr_api_url)
        self.tracker = None
        self.find_nearest = FindNearestService()
        self.arcgis_service = ArcGISService()
        self.image_processor = ImageProcessingService()
        self.image_info = ImageInfo()
        self.tenant_name = "moerenett"
        self.schema_name = "Distribusjonsnett"

        

    def upload_distribusjon_image(self, image_path, file_hash, base_attributes, resize_options=None):
        upload_result = None
        try:
            # Handle resizing if requested
            upload_path = image_path
            max_width = 7680 
            max_height = 4320
            quality = 90

            # Calculate file hash (use original path for tracking)
            #file_hash = self.image_service.calculate_file_hash(image_path, 'md5')
            
            #print(f"Checking if image {os.path.basename(image_path)} exists in ImageGrid...")
            exist_in_imagegrid = self.image_service.check_image_exists(file_hash)
            print(f"Exist in ImageGrid: {exist_in_imagegrid}")

            if exist_in_imagegrid:
                #print(f"Image {os.path.basename(image_path)} already exists in ImageGrid.")
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
                #print(f"Upload result: {upload_result}")

                if not upload_result:
                    #print(f"Failed to upload {image_path}")
                    upload_result = None
                    # continue to finally block for logging
                    status = "failed_upload"
                    log_data = self.image_info.create_nettstasjon_log_data(
                        imageinfo=dict(filename=os.path.basename(image_path), hash=file_hash),
                        filepath=image_path,
                        status=status
                    )

                    self.tracker.log_upload(log_data)
                    return status

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


            #print(f"Combined attributes for {os.path.basename(image_path)}: {base_attributes}")

            objectnumber = base_attributes.get('attributes', {}).get('ID', '')
            driftsmerking = base_attributes.get('attributes', {}).get('DRIFTSMERKING', '')
            mstasjon = base_attributes.get('attributes', {}).get('MSTASJON', '')

            #filename = combined_attributes.get('Name', '')
            longitude = base_attributes.get('geometry', {}).get('x', None)
            latitude = base_attributes.get('geometry', {}).get('y', None)

            longitude, latitude = self.arcgis_service.transform_utm_to_gps(longitude, latitude)
            
            filename = os.path.basename(image_path)

            # Use ImageInfo class to create structured data
            imageinfo = self.image_info.create_nettstasjon_info(
                filename=filename,
                navn=filename,
                latitude=latitude,
                longitude=longitude,
                objektnummer=objectnumber,
                driftsmerking=driftsmerking,
                kilde=self.kilde,
                filehash=file_hash,
                mstasjon=mstasjon
            )

            #print(f"Final image info for {filename}: {imageinfo}")
            # Update image info with toppbefaring attributes
            update_result = self.image_service.update_image_info(image_id, imageinfo, self.tenant_name, self.schema_name)
            
            print(f"Update result: {update_result}")
            
            
            if update_result == "Update failed":
                print(f"Failed to update attributes for {image_path}")
                status = "failed_update"
                #return "Update failed"
            elif exist_in_imagegrid:
                upload_result = status  # Return existing info if only attributes were updated

            # Use ImageInfo class to create log data
            log_data = self.image_info.create_nettstasjon_log_data(
                imageinfo=imageinfo,
                filepath=image_path,
                status=status
            )

            self.tracker.log_upload(log_data)
            # Update the set of existing files if upload was successful
            """ if log_data[-1] != "failed":
                self.existing_files.add(image_path) """

            print(f"Successfully uploaded and updated {imageinfo.get('filename')}")
            return upload_result

        except Exception as e:
            print(f"Error uploading {image_path}: {str(e)}")
            # Log failed upload attempt using ImageInfo class
            try:
                failed_data = self.image_info.create_failed_log_data(
                    filepath=image_path,
                    filehash=self.image_service.calculate_file_hash(image_path, 'md5') if hasattr(self, 'image_service') else 'unknown',
                    kilde=self.kilde,
                    anleggstype='Nettstasjon'
                )
                self.tracker.log_upload(failed_data)
                print(f"Logged failed upload attempt for {os.path.basename(image_path)}")
            except Exception as log_error:
                print(f"Failed to log upload error: {log_error}")
            return None


    def upload_from_folder(self, folder_path, resize_options=None):
        """
        Upload all images from a folder with toppbefaring attributes.
        base_attributes_template should be a dict with default attributes.
        If find_mast is True, will try to find nearest mast for each image.
        If resize_options is provided, will resize images before uploading.
        """
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return
        
        trackerfile = os.path.join(folder_path, "upload_log.csv")
        self.tracker = ImageUploadTracker(trackerfile)
        uploaded_count = 0
        failed_count = 0
        skipped_count = 0

        driftsmerking_from_folder = os.path.basename(folder_path).split(' ')[0]
        
        attributes = self.arcgis_service.find_nettstasjon(driftsmerking_from_folder)

        #print(f"Found attributes for driftsmerking {driftsmerking_from_folder}: {attributes}")
        if attributes is None:
            print(f"No attributes found for driftsmerking {driftsmerking_from_folder}, using defaults.")
        print(f"Using driftsmerking from folder name: {driftsmerking_from_folder}")
        
        
        #filename,latitude,longitude,anleggstype,anleggstype_n,navn,driftsmerking,erhistorisk,ergroft,kilde,nettmelding_elsmart,erutvendig,erinnvendig
       
        # Get list of image files first
        image_files = []
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    image_files.append(os.path.join(root, filename))

        total_files = len(image_files)
        print(f"Found {total_files} image files to process")
        updated_count = 0
        failed_update_count = 0

        for i, filename in enumerate(image_files, 1):
            image_path = os.path.join(folder_path, filename)
            
            filehash = self.image_service.calculate_file_hash(image_path, 'md5')
            
            print(f"Processing file {i}/{total_files}: {filename} with hash {filehash}")

            exist_in_logfile, upload_time, update_time = self.tracker.has_been_uploaded(filehash)

            if exist_in_logfile:
                skipped_count += 1
                print(f"[{i}/{total_files}] {filename}: Skipped (already uploaded)")
                continue
            #print(f"[{i}/{total_files}] Processing {filename}...")
            result = self.upload_distribusjon_image(image_path, filehash, attributes, resize_options)
            

            if result == "Skipped":
                skipped_count += 1
                #print(f"[{i}/{total_files}] {filename}: Skipped (already uploaded)")
            elif result == "updated_image":
                updated_count += 1
                #print(f"[{i}/{total_files}] {filename}: Updated (already uploaded)")
            elif result == "failed_upload" or  result is None:
                failed_count += 1
                print(f"[{i}/{total_files}] {filename}: Failed")
            elif result == "failed_update":
                failed_update_count += 1
            else:
                uploaded_count += 1
                print(f"[{i}/{total_files}] {filename}: Uploaded successfully")

        print(f"\nUpload complete:")
        print(f"  Total files: {total_files}")
        print(f"  Uploaded: {uploaded_count}")
        print(f"  Updated files: {updated_count}")
        print(f"  Skipped (already uploaded): {skipped_count}")
        print(f"  Failed updates: {failed_count}")
        print(f"  Failed: {failed_count}")



# Example usage
if __name__ == "__main__":
    
    try:


        # Get upload folder path from environment or use default
        folder_path = r"L:\Bilder til Sky-system\Nye Bilder"

        testfolder = r"L:\Bilder til Sky-system\Nye Bilder\55350 Havikbotn - test"
        
        uploader = DistribusjonUploader()
        uploader.upload_from_folder(testfolder)

        for image_folder_path in os.listdir(folder_path):
            if os.path.isdir(os.path.join(folder_path, image_folder_path)):
                print(f"Found image folder: {image_folder_path}")
                
                uploader = DistribusjonUploader()
                uploader.upload_from_folder(os.path.join(folder_path, image_folder_path))


    except Exception as main_e:
        print(f"Error in main execution: {str(main_e)}")