# ImageGrid Toppbefaring Upload

This project uploads toppbefaring images to ImageGrid and automatically links them to the nearest mast from an ArcGIS feature layer.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   - Copy `.env` file and update with your actual credentials:
   ```bash
   cp .env .env.local
   ```

   Update the following variables in your `.env` file:
   ```
   # ImageGrid Credentials
   IMAGEGRID_CLIENT_ID=your_actual_client_id
   IMAGEGRID_CLIENT_SECRET=your_actual_client_secret
   IMAGEGRID_TOKEN_URL=https://your-auth-endpoint/oauth/token
   IMAGEGRID_API_URL=https://your-imagegrid-api-endpoint

   # ArcGIS Credentials
   ARCGIS_USERNAME=your_arcgis_username
   ARCGIS_PASSWORD=your_arcgis_password
   ARCGIS_TOKEN_URL=https://map.linja.no/arcgis/tokens/generateToken
   ARCGIS_BASE_URL=https://map.linja.no/arcgis/rest/services/Volue/iAMViewer3/MapServer/5

   # Upload Configuration
   UPLOAD_FOLDER_PATH=C:\path\to\your\toppbefaring\images
   ```

3. **Run the uploader:**
   ```bash
   python toppbefaring.py
   ```

## Features

- **Automatic Mast Linking**: Extracts GPS coordinates from image EXIF data and finds the nearest mast within 50 meters
- **ArcGIS Authentication**: Handles ArcGIS token authentication automatically with token refresh
- **Image Resizing**: Resize images while preserving all EXIF data including GPS coordinates
- **Duplicate Prevention**: Checks file hash to avoid uploading the same image twice
- **Upload Tracking**: Logs all uploads with status and metadata
- **Preview Mode**: Shows which mast will be linked to each image before uploading
- **ArcGIS Integration**: Queries ArcGIS feature layer for mast information with proper authentication

## Security

- All credentials are stored in `.env` file (not committed to version control)
- `.env` file is included in `.gitignore`
- Use environment variables for all sensitive configuration

## Configuration

The system automatically maps ArcGIS mast fields to ImageGrid attributes:
- `DRIFTSMERKING` → `driftsmerking`
- `MASTENUMMER` → `mast_nummer`
- `LINJENUMMER` → `linje_nummer`
- And many more...

## Usage Examples

### Preview mast linking:
```python
uploader.preview_mast_linking(folder_path)
```

### Upload with resizing:
```python
resize_options = {
    'max_width': 1920,
    'max_height': 1080,
    'quality': 85,
    'overwrite': False  # Create resized copies instead of overwriting originals
}

uploader.upload_from_folder(folder_path, attributes_template, find_mast=True, resize_options=resize_options)
```

### Resize images only:
```python
uploader.resize_images_in_folder(folder_path, max_width=1920, max_height=1080, quality=85, overwrite=False)
```

## Configuration

The system automatically maps ArcGIS mast fields to ImageGrid attributes:
- `DRIFTSMERKING` → `driftsmerking`
- `MASTENUMMER` → `mast_nummer`
- `LINJENUMMER` → `linje_nummer`
- And many more...

## Image Resizing

The resize functionality preserves all EXIF data including GPS coordinates:

- **Aspect Ratio**: Maintains original aspect ratio
- **EXIF Preservation**: All metadata including GPS coordinates are preserved
- **Quality Control**: Configurable JPEG quality (default 85%)
- **Flexible Output**: Can overwrite originals or create resized copies
- **Smart Processing**: Only resizes images larger than target dimensions
