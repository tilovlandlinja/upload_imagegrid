import subprocess
import sys
import os
import json
from PIL import Image
import xml.etree.ElementTree as ET
import piexif

def check_exiftool():
    """
    Check if exiftool is installed.
    """
    try:
        subprocess.run(['exiftool', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def parse_dms_string(dms_str):
    """
    Parse DMS string like '59,30,7.123' to decimal degrees.
    """
    if not dms_str:
        return None
    parts = dms_str.split(',')
    if len(parts) != 3:
        return None
    degrees = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return degrees + minutes / 60 + seconds / 3600

def get_decimal_from_dms(dms, ref):
    """
    Convert DMS (Degrees, Minutes, Seconds) to decimal degrees.
    """
    try:
        if isinstance(dms, tuple) and len(dms) == 3:
            # Handle standard EXIF format: ((deg, scale), (min, scale), (sec, scale))
            if all(isinstance(coord, tuple) and len(coord) == 2 for coord in dms):
                degrees = dms[0][0] / dms[0][1]
                minutes = dms[1][0] / dms[1][1] / 60.0
                seconds = dms[2][0] / dms[2][1] / 3600.0
            else:
                # Raw format: (degrees, minutes, seconds) as simple values
                degrees = float(dms[0])
                minutes = float(dms[1]) / 60.0
                seconds = float(dms[2]) / 3600.0
        else:
            return 0.0

        decimal = degrees + minutes + seconds
        if ref in ['S', 'W']:
            decimal = -decimal
        return decimal

    except (IndexError, TypeError, ZeroDivisionError, ValueError):
        return 0.0

def print_exif_data(image_path):
    """
    Reads and prints GPS data from an image file using piexif, checks XMP, sidecar .nksc file, dumps all metadata to JSON, and saves raw EXIF data.
    """
    if not check_exiftool():
        print("exiftool is not installed. Please download and install it from https://exiftool.org/ and add it to your PATH.")
        return
    
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return
    
    try:
        # Open image with PIL for XMP and raw EXIF
        image = Image.open(image_path)
        
        # Save raw EXIF data
        if 'exif' in image.info:
            exif_file = image_path + '.exif'
            with open(exif_file, 'wb') as f:
                f.write(image.info['exif'])
            print(f"Raw EXIF data saved to {exif_file}")
        else:
            print("No EXIF data found in image.")
        
        xmp_data = image.info.get('xmp')
        if xmp_data:
            print("XMP data found:")
            print(xmp_data)
            print("\n" + "=" * 50)
            
            # Parse XMP for GPS
            try:
                root = ET.fromstring(xmp_data)
                ns = {'exif': 'http://ns.adobe.com/exif/1.0/'}
                lat_str = root.findtext('.//exif:GPSLatitude', namespaces=ns)
                lon_str = root.findtext('.//exif:GPSLongitude', namespaces=ns)
                lat_ref = root.findtext('.//exif:GPSLatitudeRef', namespaces=ns)
                lon_ref = root.findtext('.//exif:GPSLongitudeRef', namespaces=ns)
                
                if lat_str and lon_str:
                    lat = parse_dms_string(lat_str)
                    lon = parse_dms_string(lon_str)
                    
                    if lat_ref == 'S':
                        lat = -lat
                    if lon_ref == 'W':
                        lon = -lon
                    
                    print("GPS from XMP:")
                    print(f"Latitude: {lat}")
                    print(f"Longitude: {lon}")
                    print("\n" + "=" * 50)
                    return  # If found in XMP, stop here
            except Exception as e:
                print(f"Error parsing XMP: {e}")
        else:
            print("No XMP data found.")
        
        # Check for Nikon sidecar .nksc file
        sidecar_path = os.path.splitext(image_path)[0] + '.nksc'
        if os.path.exists(sidecar_path):
            print(f"Nikon sidecar file found: {sidecar_path}")
            try:
                result = subprocess.run([
                    'exiftool', 
                    '-j',  # JSON output
                    sidecar_path
                ], capture_output=True, text=True, check=True)
                
                sidecar_json = result.stdout.strip()
                sidecar_data = json.loads(sidecar_json)[0]
                
                lat = sidecar_data.get('GPSLatitude')
                lon = sidecar_data.get('GPSLongitude')
                lat_ref = sidecar_data.get('GPSLatitudeRef')
                lon_ref = sidecar_data.get('GPSLongitudeRef')
                
                if lat is not None and lon is not None:
                    if lat_ref == 1:  # South
                        lat = -abs(lat)
                    if lon_ref == 3:  # West
                        lon = -abs(lon)
                    
                    print("GPS from sidecar .nksc:")
                    print(f"Latitude: {lat}")
                    print(f"Longitude: {lon}")
                    print("\n" + "=" * 50)
                    return  # If found in sidecar, stop here
                else:
                    print("No GPS in sidecar.")
            except Exception as e:
                print(f"Error reading sidecar: {e}")
        else:
            print("No Nikon sidecar .nksc file found.")
        
        # Extract GPS from EXIF using piexif
        if 'exif' in image.info:
            exif_dict = piexif.load(image.info['exif'])
            if 'GPS' in exif_dict and exif_dict['GPS']:
                gps = exif_dict['GPS']
                if piexif.GPSIFD.GPSLatitude in gps and piexif.GPSIFD.GPSLongitude in gps:
                    lat = get_decimal_from_dms(gps[piexif.GPSIFD.GPSLatitude], 
                                             gps.get(piexif.GPSIFD.GPSLatitudeRef, b'N').decode())
                    lon = get_decimal_from_dms(gps[piexif.GPSIFD.GPSLongitude], 
                                             gps.get(piexif.GPSIFD.GPSLongitudeRef, b'E').decode())
                    
                    print("GPS from EXIF (piexif):")
                    print(f"Latitude: {lat}")
                    print(f"Longitude: {lon}")
                    print("\n" + "=" * 50)
                    return  # If found in EXIF, stop here
        
        # If no GPS found, dump all metadata
        result = subprocess.run([
            'exiftool', 
            '-j',  # JSON output
            image_path
        ], capture_output=True, text=True, check=True)
        
        json_output = result.stdout.strip()
        
        # Save to JSON file
        json_file = 'exifdump2.json'
        with open(json_file, 'w') as f:
            f.write(json_output)
        
        print(f"All metadata dumped to {json_file}")
        
        # Parse JSON for GPS (fallback)
        data = json.loads(json_output)[0]
        
        print(f"GPS data for {image_path}:")
        print("=" * 50)
        
        gps_tags = {k: v for k, v in data.items() if k.startswith('GPS')}
        if gps_tags:
            print("GPS Tags:")
            for tag, value in gps_tags.items():
                print(f"  {tag}: {value}")
            
            lat = data.get('GPSLatitude')
            lon = data.get('GPSLongitude')
            lat_ref = data.get('GPSLatitudeRef')
            lon_ref = data.get('GPSLongitudeRef')
            
            if lat is not None and lon is not None:
                if lat_ref == 'S':
                    lat = -abs(lat)
                if lon_ref == 'W':
                    lon = -abs(lon)
                print(f"\nLatitude: {lat}")
                print(f"Longitude: {lon}")
            else:
                print("\nLatitude and Longitude not found in GPS tags.")
        else:
            print("No GPS data found.")
        
        print("\n" + "=" * 50)
        
    except subprocess.CalledProcessError as e:
        print(f"Error running exiftool: {e}")
    except Exception as e:
        print(f"Error processing {image_path}: {e}")

if __name__ == "__main__":
    """ if len(sys.argv) != 2:
        print("Usage: python exif_inspector.py <image_path>")
        sys.exit(1) """

    image_path = 'T:\\Linjebefaring2014\\Netteier_SFE\\Befaring_1656\\befaringsbilder\\_SF6_7837.JPG'
    print_exif_data(image_path)