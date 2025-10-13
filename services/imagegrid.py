import requests
import os
from PIL import Image
from datetime import datetime, timedelta
import json
import hashlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ImageGridService:
    def __init__(self, client_id=None, client_secret=None, token_url=None, imgr_api_url=None):
        # Use environment variables if not provided
        self.client_id = client_id or os.getenv('IMAGEGRID_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('IMAGEGRID_CLIENT_SECRET')
        self.token_url = token_url or os.getenv('IMAGEGRID_TOKEN_URL')
        self.imgr_api_url = imgr_api_url or os.getenv('IMAGEGRID_API_URL')

        # Validate required credentials
        if not all([self.client_id, self.client_secret, self.token_url, self.imgr_api_url]):
            raise ValueError("Missing required credentials. Please set IMAGEGRID_CLIENT_ID, IMAGEGRID_CLIENT_SECRET, IMAGEGRID_TOKEN_URL, and IMAGEGRID_API_URL in your .env file or pass them as parameters.")

        self.access_token = None
        self.token_refresh_time = None
        self.tenant_name = "moerenett"

    def check_image_format(self, image_path):
        try:
            with Image.open(image_path) as img:
                # img.format gir bildeformatet som 'JPEG', 'PNG', etc.
                print(f"The file is a valid image of type: {img.format}")
                return img.format
        except IOError:
            print("The file is not a valid image.")
            return None
    
    def get_access_token(self):
        # Hvis token er gyldig, returner det
        if self.access_token and self.token_refresh_time > datetime.now():
            return self.access_token

        #print("Requesting new access token")

        # Data til POST-forespørselen for å få token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "imgr.grid.api admin.api file.api"
        }

        # Send POST-forespørselen for å få token
        response = requests.post(self.token_url, data=data)

        if response.status_code == 200:
            token_result = response.json()
            self.access_token = token_result.get("access_token")
            #print(f"Token: {self.access_token}")
            
            self.token_refresh_time = datetime.now() + timedelta(minutes=30)
            return self.access_token
        else:
            raise Exception(f"Failed to get access token: {response.text}")

    def is_image_file(self,file_path):
        """
        Sjekk om filen er et gyldig bilde.
        Returnerer True hvis det er et bilde, False ellers.
        """
        if not os.path.isfile(file_path):
            print(f"Filen {file_path} eksisterer ikke.")
            return False

        image_type = self.check_image_format( file_path )

        if image_type:
            print(f"{file_path} er et gyldig bilde av typen {image_type}.")
            return True
        else:
            print(f"{file_path} er ikke et gyldig bilde.")
            return False

    def calculate_file_hash(self, file_path, algorithm_name):
        # Åpne filen i binær modus for lesing
        with open(file_path, 'rb') as file:
            # Opprett en hash-objekt basert på algoritme-navnet
            if algorithm_name.lower() == 'md5':
                hasher = hashlib.md5()
            elif algorithm_name.lower() == 'sha1':
                hasher = hashlib.sha1()
            elif algorithm_name.lower() == 'sha256':
                hasher = hashlib.sha256()
            else:
                raise ValueError(f"Hash-algoritmen {algorithm_name} er ikke støttet.")

            # Les filen i biter og oppdater hash-objektet
            while chunk := file.read(8192):
                hasher.update(chunk)
            
            # Returner hash-verdien som en heksadesimal streng
            return hasher.hexdigest()

    def upload_image(self, image_path, fileHash):

        if not self.is_image_file(image_path):
            print(f"Opplasting avbrutt. {image_path} er ikke et gyldig bilde.")
            return None

        image_exists = self.check_image_exists(fileHash )
        if image_exists:
            print(f"Bildet {image_path} er allerede lastet opp.")
            return image_exists
        token = self.get_access_token()

        headers = {
            'Authorization': f'Bearer {token}',
            # Ikke spesifiser 'Content-Type' for multipart, requests håndterer det automatisk
        }

        # Åpne bildet i binærmodus
        with open(image_path, 'rb') as image_file:
            # Spesifiser filnavnet, filen og MIME-typen korrekt i files-dictionary
            utf8_filename = os.path.basename(image_path).encode('utf-8')
            
            files = {'file': (utf8_filename, image_file, 'image/jpeg')}
            upload_url = f"{self.imgr_api_url}/api/v1.0/moerenett/upload"

            # Send POST-forespørselen med filer
            response = requests.post(upload_url, headers=headers, files=files)

            print(response.text)

            if response.status_code == 200:
                print("Image uploaded successfully.")
                return response.json()
            else:
                error_message = response.text
                raise Exception(f"Failed to upload image: {error_message}")


    def process_record(self, from_record):
        """
        Behandler dataene i from_record ved å bygge opp en ny struktur basert på spesifikke regler.
        Konverterer lokasjonsdata hvis latitude og longitude er tilstede.
        """
        prepared_data = {}

        # Sjekk om latitude og longitude er tilstede, og bygg opp lokasjonsdata
        if "latitude" in from_record and from_record["latitude"] is not None and \
        "longitude" in from_record and from_record["longitude"] is not None:
            prepared_data["Location"] = {
                "type": "Point",
                "coordinates": [
                    float(from_record["longitude"]),
                    float(from_record["latitude"])
                ]
            }

        # Gå gjennom andre felter og legg dem til i prepared_data, ekskluder 'filename', 'longitude', og 'latitude'
        for col, value in from_record.items():
            if col not in ["filename", "longitude", "latitude"] and value is not None:
                prepared_data[col] = str(value)

        # Konverter dictionary til JSON
        json_data = json.dumps(prepared_data)
        return json_data
    

    def update_image_info(self, image_id, record, tenant_name="moerenett", schema_name="Distribusjonsnett"):
        token = self.get_access_token()

        url = f"{self.imgr_api_url}api/v1.0/{tenant_name}/{schema_name}/{image_id}/runschematasks"
        
        print(f"runschematasks_URL->>> {url}")

        #print( f"Record->>> {record}")
        # Konverter 'record' til JSON
        json_data = json.dumps(record, ensure_ascii=False)
        json_data = json_data.encode('utf-8')
        #print(f"JSON data: {json_data}")

        # Sett opp headers og innhold
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        # Send POST-forespørselen for å oppdatere bildet
        response = requests.post(url, headers=headers, data=json_data)
        print("Status code:", response.status_code)
        print(response.json())
        if response.status_code == 200:
            #   print(response.json())
            print("Update successful.")
            return response.json()
        else:
            error_message = response.text
            print(f"Failed to update image: {image_id} {error_message}")
            return "Update failed"
    

    def check_image_exists(self, fileHash):
        
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        check_url = f"{self.imgr_api_url}api/v1.0/{self.tenant_name}/search?key=filehash&value={fileHash}&skip=0&limit=50"
        response = requests.get(check_url, headers=headers)
        imageinfo = response.json()

        if response.status_code == 200:
            if len(imageinfo["results"]) == 0:
                return False
            first_image = imageinfo["results"][0]
            return first_image  # Bildet finnes
            #return True  # Bildet finnes
        
        elif response.status_code == 404:
            return False  # Bildet finnes ikke
        else:
            error_message = response.text
            raise Exception(f"Failed to check if image exists: {error_message}")

# Eksempel på hvordan du bruker klassen
if __name__ == "__main__":
    try:
        image_service = ImageGridService()

        # Last opp et bilde
        image_service.upload_image("path_to_image.jpg")

        # Oppdater informasjon om et bilde
        image_service.update_image_info(image_id="12345", new_info={"title": "Updated Title", "description": "New description"})

        # Sjekk om bildet eksisterer
        image_exists = image_service.check_image_exists(image_id="12345")
        print(f"Image exists: {image_exists}")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please ensure your .env file contains the required credentials:")
        print("- IMAGEGRID_CLIENT_ID")
        print("- IMAGEGRID_CLIENT_SECRET")
        print("- IMAGEGRID_TOKEN_URL")
        print("- IMAGEGRID_API_URL")
    except Exception as e:
        print(f"An error occurred: {e}")
