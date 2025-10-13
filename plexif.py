from PIL import Image
import piexif

def get_decimal_from_dms(dms, ref):
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
        
        
image_path = 'T:\\Linjebefaring2014\\Netteier_SFE\\Befaring_1656\\befaringsbilder\\_SF6_7858.JPG'
image_path = 'T:\\Linjebefaring2014\\Netteier_SFE\\Befaring_1656\\befaringsbilder\\_SF6_7837.JPG'

print(f"Lest bilde: {image_path}")

image = Image.open(image_path)

    
if 'exif' in image.info:
        exif_dict = piexif.load(image.info['exif'])
        if 'GPS' in exif_dict and exif_dict['GPS']:
            gps = exif_dict['GPS']
            print(f"gps keys: {gps.keys()}")
            if piexif.GPSIFD.GPSLatitude in gps and piexif.GPSIFD.GPSLongitude in gps:
                lat = gps[piexif.GPSIFD.GPSLatitude]
                lon = gps[piexif.GPSIFD.GPSLongitude]
                lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b'N').decode()
                lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b'E').decode()
                
                lat = get_decimal_from_dms(lat, lat_ref)
                lon = get_decimal_from_dms(lon, lon_ref)
                
                if lat_ref == 'S':
                    lat = -lat
                if lon_ref == 'W':
                    lon = -lon
                
                print("GPS from EXIF (piexif):")
                print(f"Latitude: {lat}")
                print(f"Longitude: {lon}")
                print("\n" + "=" * 50)
                
