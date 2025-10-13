import requests
import json
from haversine import haversine, Unit
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pyproj import Transformer

# Load environment variables
load_dotenv()

# Note: This service handles coordinate transformation between WGS84 (GPS) and UTM Zone 33N (ArcGIS layer)
# The ArcGIS layer uses ETRS89 / UTM zone 33N (EPSG:25833) coordinate system

class ArcGISService:
    def __init__(self, base_url=None, token_url=None, username=None, password=None):
        # Use environment variables if not provided
        self.base_url = base_url or os.getenv('ARCGIS_BASE_URL', "https://map.linja.no/arcgis/rest/services/Volue/iAMViewer3/MapServer/5")
        self.token_url = token_url or os.getenv('ARCGIS_TOKEN_URL', "https://map.linja.no/arcgis/tokens/generateToken")
        self.username = username or os.getenv('ARCGIS_USERNAME')
        self.password = password or os.getenv('ARCGIS_PASSWORD')
        self.request_ip = os.getenv('ARCGIS_REQUEST_IP', 'https://map.linja.no')

        self.access_token = None
        self.token_refresh_time = None
        self.query_url = f"{self.base_url}/query"

        # Initialize coordinate transformers
        # WGS84 (EPSG:4326) to UTM Zone 33N (EPSG:32633)
        self.wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True)
        # UTM Zone 33N (EPSG:32633) to WGS84 (EPSG:4326)
        self.utm_to_wgs84 = Transformer.from_crs("EPSG:32633", "EPSG:4326", always_xy=True)

    def transform_gps_to_utm(self, latitude, longitude):
        """
        Transform GPS coordinates (WGS84) to UTM Zone 33N coordinates.

        Args:
            latitude (float): Latitude in degrees
            longitude (float): Longitude in degrees

        Returns:
            tuple: (easting, northing) in meters
        """
        try:
            easting, northing = self.wgs84_to_utm.transform(longitude, latitude)
            return easting, northing
        except Exception as e:
            print(f"Error transforming GPS to UTM: {e}")
            return None, None
        
    def get_mast_by_id(self, mast_id):
        """
        Retrieve mast data by its ID.

        Args:
            mast_id (int): The ID of the mast to retrieve.

        Returns:
            dict: Mast feature data or None if not found.
        """
        where_clause = f"ID = {mast_id}"
        features = self.get_mast_data(where_clause=where_clause, out_fields="*", return_geometry=True)
        if features:
            return features[0]  # Return the first matching feature
        else:
            print(f"No mast found with ID {mast_id}")
            return None

    def transform_utm_to_gps(self, easting, northing):
        """
        Transform UTM Zone 33N coordinates to GPS coordinates (WGS84).

        Args:
            easting (float): Easting in meters
            northing (float): Northing in meters

        Returns:
            tuple: (latitude, longitude) in degrees
        """
        try:
            longitude, latitude = self.utm_to_wgs84.transform(easting, northing)
            return latitude, longitude
        except Exception as e:
            print(f"Error transforming UTM to GPS: {e}")
            return None, None

    def get_access_token(self):
        """
        Get ArcGIS access token, refreshing if necessary.
        """
        # If token is valid, return it
        if self.access_token and self.token_refresh_time and self.token_refresh_time > datetime.now():
            return self.access_token

        # Validate required credentials
        if not all([self.username, self.password, self.token_url]):
            raise ValueError("Missing ArcGIS credentials. Please set ARCGIS_USERNAME, ARCGIS_PASSWORD, and ARCGIS_TOKEN_URL in your .env file.")

        try:
            # Request new token
            data = {
                'username': self.username,
                'password': self.password,
                'client': 'requestip',
                'requestip': self.request_ip,
                'expiration': 60,  # Token valid for 60 minutes
                'f': 'json'
            }

            response = requests.post(self.token_url, data=data)
            response.raise_for_status()

            token_data = response.json()

            if 'token' in token_data:
                self.access_token = token_data['token']
                # Set refresh time to 50 minutes from now (10 minutes before expiration)
                self.token_refresh_time = datetime.now() + timedelta(minutes=50)
                return self.access_token
            else:
                error_msg = token_data.get('error', {}).get('message', 'Unknown error')
                raise Exception(f"Failed to get ArcGIS token: {error_msg}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to authenticate with ArcGIS: {e}")

    def _make_authenticated_request(self, url, params=None):
        """
        Make an authenticated request to ArcGIS API.
        """
        token = self.get_access_token()

        # Add token to params
        if params is None:
            params = {}
        params['token'] = token
        
        print(url, params)

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # If token is invalid, try refreshing once
            if response.status_code == 498:  # Invalid token
                self.access_token = None  # Force token refresh
                token = self.get_access_token()
                params['token'] = token
                response = requests.get(url, params=params)
                response.raise_for_status()
                return response.json()
            else:
                raise Exception(f"ArcGIS API request failed: {e}")

    def find_nettstasjon(self, driftsmerking):
        
        params = {
            'where': f"DRIFTSMERKING='{driftsmerking}'",
            'outFields': "*",
            'f': 'json'
        }

        try:
            nsurl = 'https://map.linja.no/arcgis/rest/services/Volue/iAMViewer3/MapServer/1/query'
            data = self._make_authenticated_request(nsurl, params)

            #print(data)

            if 'features' in data:
                ns_attributes = data['features'][0]
                
                
                #print(ns_attributes)
                return ns_attributes
            else:
                print(f"No features found. Response:")
                return []
        except Exception as e:
            print(f"Error querying ArcGIS: {e}")
            return []

            
    def get_mast_data(self, where_clause="1=1", out_fields="*", return_geometry=True):
        """
        Query the ArcGIS mast layer to get mast data.
        """
        params = {
            'where': where_clause,
            'outFields': out_fields,
            'returnGeometry': return_geometry,
            'f': 'json'
        }

        try:
            data = self._make_authenticated_request(self.query_url, params)

            if 'features' in data:
                return data['features']
            else:
                print(f"No features found. Response: {data}")
                return []

        except Exception as e:
            print(f"Error querying ArcGIS: {e}")
            return []

    def get_mast_data_near_point(self, easting, northing, distance=50, spatial_ref="25833"):
        """
        Query the ArcGIS mast layer for masts near a specific UTM point.

        Args:
            easting (float): UTM easting coordinate
            northing (float): UTM northing coordinate
            distance (float): Search distance in meters
            spatial_ref (str): Spatial reference system (default: 25833 for ETRS89/UTM33N)

        Returns:
            list: List of mast features within the search distance
        """
        # Create geometry point in UTM coordinates
        geometry = f"{{\"x\":{easting:.2f},\"y\":{northing:.2f}}}"

        """ params = {
            'geometry': geometry,
            'geometryType': 'esriGeometryPoint',
            'inSR': spatial_ref,
            'spatialRel': 'esriSpatialRelIntersects',
            'distance': distance,
            'units': 'esriSRUnit_Meter',
            'outFields': '*',
            'returnGeometry': True,
            'where': 'SPENNING = 22',
            'f': 'json'
        } """

        params = {
            'geometry': geometry,
            'geometryType': 'esriGeometryPoint',
            'inSR': spatial_ref,
            'spatialRel': 'esriSpatialRelIntersects',
            'distance': distance,
            'units': 'esriSRUnit_Meter',
            'outFields': '*',
            'returnGeometry': True,
            'f': 'json'
        }

        try:
            data = self._make_authenticated_request(self.query_url, params)

            if 'features' in data:
                return data['features']
            else:
                print(f"No features found near point ({easting:.2f}, {northing:.2f}). Response: {data}")
                return []

        except Exception as e:
            print(f"Error querying ArcGIS near point: {e}")
            return []

    def find_nearest_mast(self, latitude, longitude, max_distance=100):
        """
        Find the nearest mast to the given GPS coordinates using ArcGIS spatial query.

        The ArcGIS layer uses UTM Zone 33N coordinates, so we transform GPS coordinates
        to UTM and then use ArcGIS spatial query to find nearby masts.

        Args:
            latitude (float): Latitude in degrees (WGS84)
            longitude (float): Longitude in degrees (WGS84)
            max_distance (float): Maximum search distance in meters

        Returns:
            dict: Nearest mast feature with distance, or None if not found
        """

        #print(f"Finding nearest mast to GPS coordinates ({latitude}, {longitude}) with max distance {max_distance}m")
        if not latitude or not longitude:
            return None

        # Transform GPS coordinates to UTM
        target_easting, target_northing = self.transform_gps_to_utm(latitude, longitude)
        if target_easting is None or target_northing is None:
            #print(f"Failed to transform GPS coordinates ({latitude}, {longitude}) to UTM")
            return None

        #print(f"GPS coordinates ({latitude:.6f}, {longitude:.6f}) -> UTM ({target_easting:.2f}, {target_northing:.2f})")

        # Query ArcGIS for masts within the search distance
        nearby_masts = self.get_mast_data_near_point(target_easting, target_northing, max_distance)

        #print(f"Found {len(nearby_masts)} masts from ArcGIS within {max_distance}m")

        if not nearby_masts:
            print(f"No masts found within {max_distance}m of GPS coordinates")
            return None
        else:
            print(f"Found {len(nearby_masts)} masts within {max_distance}m of GPS coordinates")

        # Find the closest mast among the results
        nearest_mast = None
        min_distance = float('inf')

        for mast in nearby_masts:
            geometry = mast.get('geometry')
            if geometry and 'x' in geometry and 'y' in geometry:
                mast_easting = geometry['x']
                mast_northing = geometry['y']

                # Calculate Euclidean distance in UTM coordinates (meters)
                distance = ((target_easting - mast_easting) ** 2 + (target_northing - mast_northing) ** 2) ** 0.5

                #print(f"Mast ID {mast['attributes'].get('ID')} at UTM ({mast_easting:.2f}, {mast_northing:.2f}) is {distance:.2f}m away")

                if distance < min_distance:
                    min_distance = distance
                    nearest_mast = mast

        if nearest_mast:
            nearest_mast['distance'] = min_distance
            mast_attrs = self.get_mast_attributes(nearest_mast)
            #print(f"Found nearest mast: {mast_attrs.get('driftsmerking', 'Unknown')} at {min_distance:.2f}m")
            return nearest_mast
        else:
            print(f"No valid mast found within {max_distance}m of GPS coordinates")
            return None

    def get_mast_attributes(self, mast_feature):
        """
        Extract relevant attributes from a mast feature for toppbefaring.
        """
        if not mast_feature or 'attributes' not in mast_feature:
            return {}

        if not mast_feature['geometry']:
            return {}

        attrs = mast_feature['attributes']

        # Map ArcGIS fields to toppbefaring attributes
        mast_attributes = {
            'id': attrs.get('ID'),
            'objectid': attrs.get('OID'),
            'driftsmerking': attrs.get('DRIFTSMERKING'),
            'linje_nummer': attrs.get('LINJENUMMER'),
            'mast_nummer': attrs.get('MASTENUMMER'),
            'komponentnummer': attrs.get('KOMPONENTNUMMER'),
            'kommune': attrs.get('KOMMUNE'),
            'spenning': attrs.get('SPENNING'),
            'hoeyeste_sp_niv': attrs.get('HOEYESTE_SP_NIV'),
            'byggeaar': attrs.get('BYGGEAAR'),
            'mastetype': attrs.get('MASTETYPE'),
            'material': attrs.get('MATERIAL'),
            'impregnering': attrs.get('IMPREGNERING'),
            'travers_type': attrs.get('TRAVERS_TYPE'),
            'antall_stolper': attrs.get('ANTALL_STOLPER'),
            'jordtype': attrs.get('JORDTYPE'),
            'eier': attrs.get('EIER'),
            'sone': attrs.get('SONE'),
            'mstasjon': attrs.get('MSTASJON'),
            'mradial': attrs.get('MRADIAL'),
            'fellesfoeringer': attrs.get('FELLESFOERINGER'),
            'omraadenavn': attrs.get('OMRAADENAVN'),
            'anmerkning': attrs.get('ANMERKNING'),
            'merknad_inspeksjon': attrs.get('MERKNAD_INSPEKSJON'),
            'sign_inspeksjon': attrs.get('SIGN_INSPEKSJON'),
            'veilys': attrs.get('VEILYS'),
            'synlig_lengde': attrs.get('SYNLIG_LENGDE'),
            'geometry': mast_feature.get('geometry')
        }

        # Remove None values
        return {k: v for k, v in mast_attributes.items() if v is not None}

    def get_mast_gps_coordinates(self, mast_feature):
        """
        Get GPS coordinates (WGS84) for a mast feature.

        Args:
            mast_feature (dict): Mast feature from ArcGIS

        Returns:
            tuple: (latitude, longitude) or (None, None) if conversion fails
        """
        if not mast_feature or 'geometry' not in mast_feature:
            return None, None

        geometry = mast_feature['geometry']
        if 'x' in geometry and 'y' in geometry:
            easting = geometry['x']
            northing = geometry['y']
            return self.transform_utm_to_gps(easting, northing)

        return None, None

# Example usage
if __name__ == "__main__":
    try:
        arcgis_service = ArcGISService()

        # Test coordinate transformation
        latitude = 62.17279369
        longitude = 5.747185017
        print(f"Testing coordinate transformation:")
        print(f"GPS: ({latitude}, {longitude})")

        easting, northing = arcgis_service.transform_gps_to_utm(latitude, longitude)
        print(f"UTM: ({easting}, {northing})")

        # Test reverse transformation
        lat_back, lon_back = arcgis_service.transform_utm_to_gps(easting, northing)
        print(f"GPS back: ({lat_back}, {lon_back})")

        # Find nearest mast using spatial query
        print(f"\nFinding nearest mast to GPS coordinates ({latitude}, {longitude}):")
        nearest_mast = arcgis_service.find_nearest_mast(latitude, longitude)

        if nearest_mast:
            print(f"Nearest mast: {nearest_mast['attributes'].get('DRIFTSMERKING')}")
            print(f"Distance: {nearest_mast.get('distance', 0):.2f} meters")

            # Get GPS coordinates for the mast
            mast_lat, mast_lon = arcgis_service.get_mast_gps_coordinates(nearest_mast)
            if mast_lat and mast_lon:
                print(f"Mast GPS coordinates: ({mast_lat:.6f}, {mast_lon:.6f})")

            mast_attrs = arcgis_service.get_mast_attributes(nearest_mast)
            print(f"Mast attributes: {mast_attrs}")
        else:
            print("No nearby mast found")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please ensure your .env file contains the required ArcGIS credentials:")
        print("- ARCGIS_USERNAME")
        print("- ARCGIS_PASSWORD")
        print("- ARCGIS_TOKEN_URL")
    except Exception as e:
        print(f"An error occurred: {e}")
