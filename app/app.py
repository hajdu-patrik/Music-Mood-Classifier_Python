import sys
import os
from flask import Flask, render_template, request, Response
import traceback

# --- Path Setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# --- Flask App Setup ---
app = Flask(__name__, template_folder='../template', static_folder='../static')

# --- Site Identity ---
# Absolute base URL of the deployment, used for canonical links, social tags, robots and the sitemap.
SITE_URL = os.environ.get('SITE_URL', 'https://music-mood-classifier-nine.vercel.app').rstrip('/')


@app.context_processor
def inject_site_urls():
    """Expose the site and the current canonical URL to every template."""
    return {'site_url': SITE_URL, 'canonical_url': SITE_URL + request.path}


# --- Initialization & Safe Loading ---
bl = None
artifacts = None
system_error = None

print("Attempting to import business_logic...")
try:
    import business_logic as bl_module
    bl = bl_module
    print("Import successful. Initializing artifacts...")
    
    try:
        # Load the heavy data (Matrix & JSON) into memory once at startup
        artifacts = bl.initialize_app()
        if artifacts is None:
            system_error = "Artifacts loaded but returned None. Check file paths in business_logic."
        else:
            print("Initialization complete.")
            
    except Exception as e:
        system_error = f"Error during initialize_app: {str(e)}\nTraceback:\n{traceback.format_exc()}"

except Exception as e:
    # This catches missing modules (e.g., if scipy is not installed)
    system_error = f"CRITICAL: Could not import business_logic.py.\nError: {str(e)}\nTraceback:\n{traceback.format_exc()}"


# --- Web Routes ---
@app.route('/')
def index():
    # Renders the main search page
    return render_template('index.html')

# --- Debug and Error Handling Routes ---
@app.route('/debug')
def debug_page():
    # Useful for checking system health in production without logs
    if system_error:
        return f"<h1>System Error</h1><pre>{system_error}</pre>", 500
    if artifacts is None:
         return "<h1>Warning</h1><p>System loaded, but artifacts are None.</p>", 500
    return "<h1>System OK</h1><p>Business logic loaded and artifacts ready.</p>"

# --- Search Route ---
@app.route('/search')
def search():
    # 1. Check system health before processing
    if system_error:
        return f"<h1>System Error</h1><p>The application failed to start correctly.</p><pre>{system_error}</pre>"
    
    if artifacts is None:
        return "<h1>Error</h1><p>Artifacts are missing (None). Please check logs.</p>"

    # 2. Get query parameters
    artist_name = request.args.get('artist')
    song_name = request.args.get('song')

    results = None
    try:
        if artist_name and song_name:
            # 3. Call the recommendation engine
            results = bl.get_recommendations(
                artist_name,
                song_name, 
                artifacts["lyrics_df"], 
                artifacts["tfidf_matrix"]
            )
        
        return render_template(
            'results.html', 
            artist=artist_name,
            song=song_name,
            results=results
        )
    except Exception:
        # Catch unexpected runtime errors during search
        return f"<h1>Runtime Error during Search</h1><pre>{traceback.format_exc()}</pre>"

# --- Crawler Routes ---
@app.route('/robots.txt')
def robots_txt():
    # Everything is public; point crawlers at the sitemap.
    body = 'User-agent: *\nAllow: /\nDisallow: /debug\nDisallow: /search\nSitemap: ' + SITE_URL + '/sitemap.xml\n'
    return Response(body, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    urls = ''.join('  <url><loc>' + SITE_URL + path + '</loc></url>\n' for path in ['/'])
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '</urlset>\n'
    return Response(body, mimetype='application/xml')


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(_):
    return render_template('404.html'), 404

# --- Application Startpoint ---
if __name__ == '__main__':
    # Only runs when executed locally (python app/app.py)
    app.run(debug=True, host='0.0.0.0', port=5000)