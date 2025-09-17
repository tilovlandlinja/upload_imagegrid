from haversine import haversine, Unit
from PIL import Image
import piexif
import pandas as pd

class FindNearestService:
    def __init__(self):
        pass

    def get_decimal_from_dms(self, dms, ref):
        """
        Konverterer DMS (Degrees, Minutes, Seconds) til desimalgrader.
        ref er 'N' eller 'S' for latitude, 'E' eller 'W' for longitude.
        """
        degrees = dms[0][0] / dms[0][1]
        minutes = dms[1][0] / dms[1][1] / 60.0
        seconds = dms[2][0] / dms[2][1] / 3600.0

        decimal = degrees + minutes + seconds
        if ref in ['S', 'W']:
            decimal = -decimal
        return decimal

    def get_gps_from_image(self, image_path):
        """
        Leser GPS-informasjon (latitude og longitude) fra EXIF-dataene til et bilde.
        """
        # Åpne bildet og hent EXIF-data
        try:
            
            image = Image.open(image_path)
            exif_data = piexif.load(image.info['exif'])

            # Hent GPS-data fra EXIF
            gps_data = exif_data.get('GPS')

            if gps_data:
                # Hent latitude og longitude fra GPS-dataene
                gps_latitude = gps_data[piexif.GPSIFD.GPSLatitude]
                gps_latitude_ref = gps_data[piexif.GPSIFD.GPSLatitudeRef].decode()
                gps_longitude = gps_data[piexif.GPSIFD.GPSLongitude]
                gps_longitude_ref = gps_data[piexif.GPSIFD.GPSLongitudeRef].decode()

                # Konverter til desimalgrader
                lat = self.get_decimal_from_dms(gps_latitude, gps_latitude_ref)
                lon = self.get_decimal_from_dms(gps_longitude, gps_longitude_ref)

                return lat, lon
            else:
                print("Ingen GPS-informasjon funnet i bildet.")
                return None, None
        except KeyError:
            print("Bilde mangler EXIF-informasjon.")
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