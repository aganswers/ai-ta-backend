"""
Tool-based code execution for file processing with persistent environment.
"""

import os
import io
import sys
import contextlib
import traceback
import re
import base64
from datetime import datetime
from typing import Dict, Any, Optional, Union
import pandas as pd
import numpy as np
import requests
import json

try:
    import geopandas as gpd
except ImportError:
    gpd = None

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
except ImportError:
    matplotlib = None
    plt = None
    Figure = None

try:
    import shapely
except ImportError:
    shapely = None

try:
    import pyproj
except ImportError:
    pyproj = None

try:
    import fiona
except ImportError:
    fiona = None

from supabase import create_client, Client


# Global execution environment
_execution_globals = None
_execution_locals = None
_plot_directory = "plots"
_supabase_client = None


def setup_execution_environment(preloaded_dataframes: Optional[Dict[str, Union[pd.DataFrame, Any]]] = None):
    """
    Set up the persistent execution environment with preloaded dataframes.
    
    Args:
        preloaded_dataframes: Dictionary mapping filenames to pandas DataFrames or geopandas GeoDataFrames
    """
    global _execution_globals, _execution_locals
    
    # Initialize Supabase client if environment variables are available
    initialize_supabase_client()
    
    # Initialize execution environment with libraries and helper functions
    _execution_globals = {
        "pd": pd,
        "np": np,
        "gpd": gpd,
        "plt": plt,
        "Figure": Figure if Figure else None,
        "shapely": shapely,
        "pyproj": pyproj,
        "fiona": fiona,
        "os": os,
        "re": re,
        "json": json,
        "datetime": datetime,
        "__builtins__": __builtins__,
        # Add helper functions
        "get_weather": get_weather,
        "get_coordinates": get_coordinates,
        "sheet_to_df": sheet_to_df,
        "current_date": lambda: datetime.now().strftime("%Y-%m-%d"),
        "current_datetime": lambda: datetime.now().isoformat(),
        "save_plot": save_plot,
        "list_dataframes": list_dataframes,
        "data_info": data_info,
    }
    
    _execution_locals = {}
    
    # Add preloaded dataframes to execution environment
    if preloaded_dataframes:
        for filename, df in preloaded_dataframes.items():
            # Create clean variable name from filename
            var_name = os.path.splitext(os.path.basename(filename))[0]
            var_name = re.sub(r'[^a-zA-Z0-9_]', '_', var_name)
            
            # Add prefix based on file type
            if gpd and isinstance(df, gpd.GeoDataFrame):
                var_name = f"gdf_{var_name}"
            else:
                var_name = f"df_{var_name}"
            
            # Add to execution environment
            _execution_globals[var_name] = df


def get_coordinates(location: str) -> tuple[float, float]:
    """Get coordinates from location string using geocoding API."""
    try:
        # Simple geocoding using Nominatim (OpenStreetMap)
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="aganswers_agent")
        location_data = geolocator.geocode(location)
        if location_data and hasattr(location_data, 'latitude') and hasattr(location_data, 'longitude'):
            return float(location_data.latitude), float(location_data.longitude)
    except Exception:
        pass
    
    # Fallback to a simple US zip code lookup if it's a 5-digit number
    if location.isdigit() and len(location) == 5:
        try:
            import pgeocode
            nomi = pgeocode.Nominatim('us')
            response = nomi.query_postal_code(location)
            if hasattr(response, 'latitude') and not pd.isna(response.latitude):
                return float(response.latitude), float(response.longitude)
        except Exception:
            pass
    
    raise ValueError(f"Could not find coordinates for location: {location}")


def get_weather(location: str) -> dict:
    """Get weather data for a given location (city or zip code)."""
    try:
        lat, lon = get_coordinates(location)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,wind_speed_10m,precipitation",
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        
        # Format the response
        current = weather_data.get("current", {})
        hourly = weather_data.get("hourly", {})
        
        return {
            "success": True,
            "location": location,
            "coordinates": {"latitude": lat, "longitude": lon},
            "current_weather": {
                "temperature_celsius": current.get("temperature_2m"),
                "temperature_fahrenheit": (current.get("temperature_2m", 0) * 9/5) + 32 if current.get("temperature_2m") else None,
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "wind_speed_mph": current.get("wind_speed_10m", 0) * 0.621371 if current.get("wind_speed_10m") else None,
                "precipitation_mm": current.get("precipitation"),
                "time": current.get("time")
            },
            "hourly_forecast": [{
                "time": hourly["time"][i] if i < len(hourly.get("time", [])) else None,
                "temperature_celsius": hourly["temperature_2m"][i] if i < len(hourly.get("temperature_2m", [])) else None,
                "humidity_percent": hourly["relative_humidity_2m"][i] if i < len(hourly.get("relative_humidity_2m", [])) else None,
                "wind_speed_kmh": hourly["wind_speed_10m"][i] if i < len(hourly.get("wind_speed_10m", [])) else None,
                "precipitation_mm": hourly["precipitation"][i] if i < len(hourly.get("precipitation", [])) else None,
            } for i in range(min(24, len(hourly.get("time", []))))]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def sheet_to_df(url_or_id: str, gid: Optional[str] = None, **read_csv_kwargs) -> pd.DataFrame:
    """Load a Google Sheet as CSV via the export endpoint (public sheets only)."""
    sheet_id = url_or_id
    m = re.search(r'/spreadsheets/d/([A-Za-z0-9_-]+)', str(url_or_id))
    if m:
        sheet_id = m.group(1)
        if gid is None:
            m2 = re.search(r'\bgid=(\d+)', str(url_or_id))
            if m2:
                gid = m2.group(1)
    if gid is None:
        gid = "0"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    return pd.read_csv(csv_url, **read_csv_kwargs)


def save_plot(filename: Optional[str] = None, fmt: str = 'png', dpi: int = 300) -> str:
    """Save the current matplotlib figure to Supabase storage and return the public URL."""
    global _plot_directory, _supabase_client
    
    if not plt:
        return "Matplotlib not available"
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"plot_{timestamp}"
    
    if not filename.endswith(f'.{fmt}'):
        filename = f'{filename}.{fmt}'
    
    # Save locally first
    os.makedirs(_plot_directory, exist_ok=True)
    filepath = os.path.join(_plot_directory, filename)
    
    plt.savefig(filepath, dpi=dpi, bbox_inches='tight')
    plt.close()
    
    # Initialize Supabase client if not already available
    if _supabase_client is None:
        _supabase_client = initialize_supabase_client()
    
    # Try to upload to Supabase if client is available
    if _supabase_client:
        try:
            # Get bucket name from environment
            bucket_name = os.environ.get('SUPABSE_PLOT_BUCKET_NAME', 'llm_output')
            
            # Read the saved file
            with open(filepath, 'rb') as f:
                img_data = f.read()
            
            # Upload to Supabase storage
            storage_path = filename
            _supabase_client.storage.from_(bucket_name).upload(
                storage_path,
                img_data,
                {"content-type": f"image/{fmt}"}
            )
            
            # Get the public URL
            public_url = _supabase_client.storage.from_(bucket_name).get_public_url(storage_path)
            
            # Clean up local file
            os.remove(filepath)
            print(f"Plot saved to Supabase: {public_url}")
            return f'Plot saved to Supabase: {public_url}'
        except Exception as e:
            # If Supabase upload fails, return local file path
            return f'Plot saved locally as {filepath} (Supabase upload failed: {str(e)})'
    else:
        return f'Plot saved locally as {filepath} (Supabase client not available)'


def list_dataframes() -> str:
    """List all available dataframes in the execution environment."""
    global _execution_globals, _execution_locals
    
    dataframes = []
    all_vars = {}
    if _execution_globals:
        all_vars.update(_execution_globals)
    if _execution_locals:
        all_vars.update(_execution_locals)
    
    for name, var in all_vars.items():
        if isinstance(var, pd.DataFrame) and not name.startswith("_"):
            df_type = "GeoDataFrame" if gpd and isinstance(var, gpd.GeoDataFrame) else "DataFrame"
            dataframes.append(f"- {name}: {df_type} ({var.shape[0]} rows × {var.shape[1]} columns)")
    
    if dataframes:
        return "Available dataframes:\n" + "\n".join(dataframes)
    else:
        return "No dataframes available in the execution environment."


def data_info(name: str) -> str:
    """Get detailed information about a specific dataframe."""
    global _execution_globals, _execution_locals
    
    all_vars = {}
    if _execution_globals:
        all_vars.update(_execution_globals)
    if _execution_locals:
        all_vars.update(_execution_locals)
    
    if name not in all_vars:
        return f"Dataset '{name}' not found."
    
    df = all_vars[name]
    if not isinstance(df, pd.DataFrame):
        return f"'{name}' is not a DataFrame."
    
    is_gdf = bool(gpd and isinstance(df, gpd.GeoDataFrame))
    info = []
    info.append(f"Dataset: {name}")
    info.append(f"Type: {'GeoDataFrame' if is_gdf else 'DataFrame'}")
    info.append(f"Shape: {df.shape}")
    info.append(f"Columns: {list(df.columns)}")
    if is_gdf and hasattr(df, 'crs'):
        info.append(f"CRS: {df.crs}")
    
    return "\n".join(info)


def set_plot_directory(directory: str):
    """Set the directory for saving plots."""
    global _plot_directory
    _plot_directory = directory
    os.makedirs(directory, exist_ok=True)


def set_supabase_client(client: Optional[Client] = None):
    """Set the Supabase client for saving outputs."""
    global _supabase_client
    _supabase_client = client


def initialize_supabase_client():
    """Initialize Supabase client from environment variables if available."""
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_API_KEY')
        
        if supabase_url and supabase_key:
            _supabase_client = create_client(supabase_url, supabase_key)
            print(f"Supabase client initialized with URL: {supabase_url}")
            return _supabase_client
        else:
            print("Supabase environment variables not found, client not initialized")
            return None
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None


def run_code(reasoning: str, code: str) -> str:
    """
    Execute Python code in the persistent environment and return results.
    
    This tool allows the agent to execute Python code for data analysis and visualization.
    The execution environment persists between calls, maintaining variable state.
    
    Args:
        reasoning: Brief explanation of what the code will do
        code: Python code to execute
        
    Returns:
        String containing execution output, results, and any error messages
    """
    global _execution_globals, _execution_locals, _plot_directory, _supabase_client
    
    if _execution_globals is None:
        return "Error: Execution environment not initialized. Please contact support."
    
    print(f"[Code Execution] Reasoning: {reasoning}")
    
    # Capture stdout and stderr
    stdout_buffer = io.StringIO()
    
    try:
        # Execute the code
        with (
            contextlib.redirect_stdout(stdout_buffer),
            contextlib.redirect_stderr(stdout_buffer),
        ):
            exec(code, _execution_globals, _execution_locals)
            
            # Handle figure outputs
            figure_count = 0
            
            # Check for any matplotlib figures
            if plt:
                for fig_num in plt.get_fignums():
                    figure_count += 1
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"figure_{timestamp}_{figure_count}.png"
                    
                    os.makedirs(_plot_directory, exist_ok=True)
                    filepath = os.path.join(_plot_directory, filename)
                    
                    plt.figure(fig_num)
                    plt.savefig(filepath, dpi=150, bbox_inches='tight')
                    plt.close(fig_num)
                    
                    stdout_buffer.write(f"\n[Figure {figure_count} saved: {filepath}]")
                    
                    # Initialize Supabase client if not already available
                    if _supabase_client is None:
                        _supabase_client = initialize_supabase_client()
                    
                    # Try to upload to Supabase if client is available
                    if _supabase_client:
                        try:
                            with open(filepath, 'rb') as f:
                                img_data = f.read()
                            
                            bucket_name = os.environ.get('SUPABSE_PLOT_BUCKET_NAME', 'llm_output')
                            storage_path = filepath.replace("plots/", "")
                            _supabase_client.storage.from_(bucket_name).upload(
                                storage_path,
                                img_data,
                                {"content-type": "image/png"}
                            )
                            
                            file_url = _supabase_client.storage.from_(bucket_name).get_public_url(storage_path)
                            stdout_buffer.write(f" [URL: {file_url}]")
                        except Exception as e:
                            stdout_buffer.write(f" [Upload failed: {str(e)}]")
        
        # Get output
        output = stdout_buffer.getvalue()
        
        # If no output, show some key variables from the last execution
        if not output.strip():
            result_vars = []
            for var_name, var_value in _execution_locals.items() if _execution_locals else {}:
                if var_name.startswith("_") or callable(var_value):
                    continue
                    
                if isinstance(var_value, pd.DataFrame):
                    result_vars.append(f"\n--- {var_name} ---\n{var_value.head().to_string()}")
                    if len(var_value) > 5:
                        result_vars.append(f"[{len(var_value)-5} more rows]")
                elif not isinstance(var_value, type):
                    var_str = str(var_value)
                    if len(var_str) > 500:
                        var_str = var_str[:500] + "... [truncated]"
                    result_vars.append(f"{var_name} = {var_str}")
            
            if result_vars:
                output = "\n".join(result_vars[-5:])  # Show last 5 results
        
        return f"```python\n{code}\n```\n\nOutput:\n{output}"
        
    except Exception as e:
        # Format error message
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        # Filter traceback to focus on the error
        error_message = "".join(tb_lines[-3:])  # Last 3 lines usually contain the actual error
        
        return f"```python\n{code}\n```\n\nError:\n{error_message}"
        
    finally:
        if plt:
            plt.close("all")
        stdout_buffer.close()


def generate_dataframes_info(preloaded_dataframes: dict) -> str:
    """
    Generate information about available dataframes for the agent prompt.
    
    Args:
        preloaded_dataframes: Dictionary mapping filenames to pandas DataFrames or geopandas GeoDataFrames
    
    Returns:
        A formatted string containing information about all available dataframes
    """
    if not preloaded_dataframes:
        return "No dataframes are currently available."
    
    result = []
    result.append("**Available Dataframes:**")
    result.append("")
    
    for filename, df in preloaded_dataframes.items():
        # Create clean variable name from filename
        var_name = os.path.splitext(os.path.basename(filename))[0]
        var_name = re.sub(r'[^a-zA-Z0-9_]', '_', var_name)
        
        # Add prefix based on file type
        if gpd and isinstance(df, gpd.GeoDataFrame):
            var_name = f"gdf_{var_name}"
            df_type = "GeoDataFrame"
            geometry_info = str(df.geometry.geom_type.value_counts().to_dict()) if hasattr(df, 'geometry') else "N/A"
            crs_info = f"CRS: {df.crs}" if hasattr(df, 'crs') else "CRS: N/A"
        else:
            var_name = f"df_{var_name}"
            df_type = "DataFrame" 
            geometry_info = "N/A"
            crs_info = "N/A"
        
        result.append(f"* **{filename}** → `{var_name}`")
        result.append(f"  - Type: {df_type}")
        result.append(f"  - Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        if isinstance(df, pd.DataFrame):
            result.append(f"  - Columns: {', '.join(list(df.columns)[:10])}")
            if len(df.columns) > 10:
                result.append(f"    ... and {len(df.columns) - 10} more columns")
        if gpd and isinstance(df, gpd.GeoDataFrame):
            result.append(f"  - Geometry Types: {geometry_info}")
            result.append(f"  - {crs_info}")
        result.append("")
    
    return "\n".join(result)