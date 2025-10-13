from haversine import haversine, Unit
from PIL import Image
import piexif
import pandas as pd

class FindNearestService:
    def __init__(self):
        pass

    def validate_coordinates(self, lat, lon):
        """
        Validerer at GPS koordinater er rimelige.
        """
        # Check if coordinates are within valid ranges
        if not (-90 <= lat <= 90):
            return False
        if not (-180 <= lon <= 180):
            return False

        # Check if coordinates are not (0,0) which often indicates invalid GPS
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            return False

        return True

    def get_decimal_from_dms(self, dms, ref):
        """
        Konverterer DMS (Degrees, Minutes, Seconds) til desimalgrader.
        ref er 'N' eller 'S' for latitude, 'E' eller 'W' for longitude.

        Håndterer forskjellige EXIF-formater:
        - Standard format: ((degrees, scale), (minutes, scale), (seconds, scale))
        - Raw format: ((deg, scale), (min, scale), (sec, scale)) - som bruker ser
        - Simple format: (degrees, minutes, seconds) som tuples
        """
        try:
            if isinstance(dms, tuple) and len(dms) == 3:
                # Handle standard EXIF format: ((deg, scale), (min, scale), (sec, scale))
                if all(isinstance(coord, tuple) and len(coord) == 2 for coord in dms):
                    degrees = dms[0][0] / dms[0][1]
                    minutes = dms[1][0] / dms[1][1] / 60.0
                    seconds = dms[2][0] / dms[2][1] / 3600.0
                    print(f"Konverterer standard EXIF format: {dms} -> {degrees}° + {minutes}' + {seconds}\" = {degrees + minutes + seconds}")
                else:
                    # Raw format: (degrees, minutes, seconds) as simple values
                    degrees = float(dms[0])
                    minutes = float(dms[1]) / 60.0
                    seconds = float(dms[2]) / 3600.0
                    print(f"Konverterer raw format: {dms} -> {degrees}° + {minutes}' + {seconds}\" = {degrees + minutes + seconds}")
            else:
                # Fallback for unexpected formats
                print(f"Uventet DMS format: {dms}, type: {type(dms)}")
                return 0.0

            decimal = degrees + minutes + seconds
            if ref in ['S', 'W']:
                decimal = -decimal
            return decimal

        except (IndexError, TypeError, ZeroDivisionError, ValueError) as e:
            print(f"Feil ved DMS-konvertering: {e}, DMS: {dms}, ref: {ref}")
            return 0.0

    def get_gps_from_image(self, image_path):
        """
        Leser GPS-informasjon (latitude og longitude) fra EXIF-dataene til et bilde.
        """
        try:
            image = Image.open(image_path)

            
            
            # Check if image has EXIF data
            if 'exif' not in image.info:
                print(f"Ingen EXIF-data funnet i bildet: {image_path}")
                return None, None

            # Load EXIF data
            exif_data = piexif.load(image.info['exif'])

            # Check if GPS data exists
            gps_data = exif_data.get('GPS')
            
            if not gps_data:
                print(f"Ingen GPS-data funnet i EXIF for bildet: {image_path}")
                return None, None

            # Debug: Print GPS data structure
            print(f"GPS data for {image_path}: {gps_data}")

            # Check if required GPS fields exist and handle different formats
            gps_latitude = None
            gps_longitude = None
            gps_latitude_ref = 'N'
            gps_longitude_ref = 'E'

            # Try standard EXIF GPS tags first
            if piexif.GPSIFD.GPSLatitude in gps_data:
                gps_latitude = gps_data[piexif.GPSIFD.GPSLatitude]
            if piexif.GPSIFD.GPSLongitude in gps_data:
                gps_longitude = gps_data[piexif.GPSIFD.GPSLongitude]

            # Try reference directions
            if piexif.GPSIFD.GPSLatitudeRef in gps_data:
                gps_latitude_ref = gps_data[piexif.GPSIFD.GPSLatitudeRef].decode()
            if piexif.GPSIFD.GPSLongitudeRef in gps_data:
                gps_longitude_ref = gps_data[piexif.GPSIFD.GPSLongitudeRef].decode()

            # If standard tags don't work, try raw GPS data (keys 2 and 4)
            if gps_latitude is None and 2 in gps_data:
                gps_latitude = gps_data[2]
                print(f"Bruker raw GPS latitude data: {gps_latitude}")
            if gps_longitude is None and 4 in gps_data:
                gps_longitude = gps_data[4]
                print(f"Bruker raw GPS longitude data: {gps_longitude}")

            # Try to get reference directions from raw data if available
            if 1 in gps_data:  # GPSLatitudeRef
                gps_latitude_ref = gps_data[1].decode() if isinstance(gps_data[1], bytes) else str(gps_data[1])
            if 3 in gps_data:  # GPSLongitudeRef
                gps_longitude_ref = gps_data[3].decode() if isinstance(gps_data[3], bytes) else str(gps_data[3])

            if gps_latitude is None or gps_longitude is None:
                print(f"GPS koordinater mangler i EXIF for bildet: {image_path}")
                return None, None

            # Convert to decimal degrees
            lat = self.get_decimal_from_dms(gps_latitude, gps_latitude_ref)
            lon = self.get_decimal_from_dms(gps_longitude, gps_longitude_ref)

            # Validate coordinates
            if not self.validate_coordinates(lat, lon):
                print(f"Ugyldige GPS koordinater for {image_path}: lat={lat}, lon={lon}")
                return None, None

            print(f"Vellykket GPS ekstraksjon for {image_path}: lat={lat}, lon={lon}")
            return lat, lon

        except KeyError as e:
            print(f"EXIF KeyError for {image_path}: {e}")
            return None, None
        except Exception as e:
            print(f"Feil ved EXIF-lesing for {image_path}: {e}")
            return None, None
        
    def find_nearest(self, image_path, df):
        """
        Funksjon for å finne nærmeste rad basert på GPS-koordinater fra bildet og en DataFrame.
        """
        # Hent GPS-koordinatene fra bildet
        image_coords = self.get_gps_from_image(image_path)

        #print(f"GPS-koordinater fra bildet: {image_coords}")
        if image_coords == (None, None):
            return None

        # Lag en funksjon for å beregne avstanden mellom bildet og hver rad i DataFrame
        def calculate_distance(row):
            point = (row['latitude'], row['longitude'])
            return haversine(image_coords, point, unit=Unit.METERS)

        # Bruk apply for å beregne avstanden mellom bildet og hver rad i DataFrame
        df['distance'] = df.apply(calculate_distance, axis=1)

        # Finn raden med den minste avstanden
        nearest_row = df.loc[df['distance'].idxmin()]
        
        #print(f"GPS-koordinater fra skapet: ( {nearest_row['latitude']}, {nearest_row['longitude']} )")
        #print(f"Nærmeste treff er på avstand: {nearest_row['distance']} m")

        if nearest_row['distance'] < 50:  # Juster terskelen etter behov
            return nearest_row
        else:
            return None
        
# Eksempel på bruk
if __name__ == "__main__":
    # Path til CSV-filen
    csv_file_path = 'path_to_your_csv_file.csv'

    # Les CSV-filen inn i en DataFrame
    df = pd.read_csv(csv_file_path)

    # Opprett tjenesten og bruk den
    service = FindNearestService()

    # Path til bildet
    image_path = "path_to_your_image.jpg"
    
    # Finn nærmeste koordinat fra bildet
    nearest_result = service.find_nearest(image_path, df)
    
    if nearest_result is not None:
        print(nearest_result)