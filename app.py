from flask import Flask, render_template, request, jsonify, send_file
import json
import os
from datetime import datetime, timedelta
import calendar
from indiarace_scraper import IndiaraceMonthlyScraper

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Initialize scraper
scraper = IndiaraceMonthlyScraper()

# Data storage
DATA_DIR = "indiarace_monthly"
os.makedirs(DATA_DIR, exist_ok=True)

@app.route('/')
def index():
    """Main page with calendar interface"""
    return render_template('index.html')

@app.route('/api/month_data/<int:year>/<int:month>')
def get_month_data(year, month):
    """API endpoint to get month data"""
    try:
        # Check if data file exists
        json_file = os.path.join(DATA_DIR, f"indiarace_{year}-{month:02d}_complete.json")
        
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            # Scrape data if not exists
            print(f"Scraping new data for {year}-{month:02d}")
            monthly_data = scraper.scrape_month(year, month)
            scraper.save_monthly_data(monthly_data, DATA_DIR)
            return jsonify(monthly_data)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape_month', methods=['POST'])
def scrape_month():
    """Trigger scraping for a specific month"""
    try:
        data = request.get_json()
        year = data.get('year')
        month = data.get('month')
        venues = data.get('venues', list(scraper.venues.keys()))
        race_types = data.get('race_types', ['RACECARD'])
        
        if not year or not month:
            return jsonify({'error': 'Year and month are required'}), 400
        
        # Scrape the data
        monthly_data = scraper.scrape_month(year, month, venues, race_types)
        scraper.save_monthly_data(monthly_data, DATA_DIR)
        
        return jsonify({
            'success': True,
            'message': f'Successfully scraped {monthly_data["total_races"]} races for {monthly_data["month_name"]}',
            'data': monthly_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar_data/<int:year>/<int:month>')
def get_calendar_data(year, month):
    """Get calendar with race counts for each day"""
    try:
        # Check if data file exists
        json_file = os.path.join(DATA_DIR, f"indiarace_{year}-{month:02d}_complete.json")
        
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            calendar_data = {}
            for day_data in data.get('data', []):
                total_races = 0
                for venue in day_data.get('venues', []):
                    total_races += venue.get('race_count', 0)
                
                calendar_data[day_data['date']] = {
                    'races': total_races,
                    'has_data': total_races > 0
                }
            
            return jsonify(calendar_data)
        else:
            return jsonify({})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/race_details/<race_id>')
def get_race_details(race_id):
    """Get detailed information for a specific race"""
    try:
        # Search through all available data files
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('_complete.json'):
                file_path = os.path.join(DATA_DIR, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Search for the race
                for day_data in data.get('data', []):
                    for venue in day_data.get('venues', []):
                        for race in venue.get('races', []):
                            if f"{venue['date']}-race-{race['race_number']}" == race_id:
                                return jsonify(race)
        
        return jsonify({'error': 'Race not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/venues')
def get_venues():
    """Get list of all venues"""
    return jsonify(scraper.venues)

@app.route('/month/<int:year>/<int:month>')
def month_view(year, month):
    """Display month view with all races"""
    return render_template('month_view.html', year=year, month=month)

@app.route('/race/<race_id>')
def race_view(race_id):
    """Display detailed race view"""
    return render_template('race_view.html', race_id=race_id)

@app.route('/download/<int:year>/<int:month>/<format>')
def download_data(year, month, format):
    """Download month data in different formats"""
    try:
        month_str = f"{year}-{month:02d}"
        
        if format == 'json':
            file_path = os.path.join(DATA_DIR, f"indiarace_{month_str}_complete.json")
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, 
                               download_name=f"indiarace_{month_str}.json")
        
        elif format == 'csv':
            file_path = os.path.join(DATA_DIR, f"indiarace_{month_str}.csv")
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True,
                               download_name=f"indiarace_{month_str}.csv")
        
        elif format == 'races':
            file_path = os.path.join(DATA_DIR, f"indiarace_{month_str}_races.json")
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True,
                               download_name=f"indiarace_{month_str}_races.json")
        
        else:
            return jsonify({'error': 'Invalid format'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/available_months')
def get_available_months():
    """Get list of months with available data"""
    try:
        months = []
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('_complete.json'):
                # Extract year and month from filename
                parts = filename.replace('indiarace_', '').replace('_complete.json', '').split('-')
                if len(parts) == 2:
                    year, month = int(parts[0]), int(parts[1])
                    months.append({
                        'year': year,
                        'month': month,
                        'month_name': datetime(year, month, 1).strftime('%B %Y'),
                        'file': filename
                    })
        
        # Sort by date
        months.sort(key=lambda x: (x['year'], x['month']), reverse=True)
        return jsonify(months)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)