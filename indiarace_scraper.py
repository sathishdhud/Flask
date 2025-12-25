import requests
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime, timedelta
import csv
import os
from urllib.parse import urljoin

class IndiaraceMonthlyScraper:
    def __init__(self):
        self.base_url = "https://www.indiarace.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Venue IDs and names
        self.venues = {
            1: "Mumbai",
            2: "Kolkata", 
            3: "Bangalore",
            4: "Hyderabad",
            5: "Pune",
            6: "Mysore",
            7: "Delhi",
            8: "Ooty",
            9: "Chennai"
        }
        
        # Race types
        self.race_types = ["RACECARD", "RESULTS"]
        
        # Statistics
        self.total_races_scraped = 0
        self.total_horses_scraped = 0
        self.failed_requests = 0
    
    def fetch_race_data(self, venue_id, event_date, race_type="RACECARD", max_retries=3):
        """
        Fetch race data with retry mechanism
        """
        url = f"{self.base_url}/Home/racingCenterEvent"
        params = {
            'venueId': venue_id,
            'event_date': event_date,
            'race_type': race_type
        }
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                # Check if page has actual race data
                if "No races found for this date" in response.text or "No races scheduled" in response.text:
                    return None
                
                return self.parse_race_html(response.text, venue_id, event_date)
                
            except requests.RequestException as e:
                print(f"Attempt {attempt + 1} failed for {self.venues.get(venue_id)} on {event_date}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.failed_requests += 1
                    return None
    
    def parse_race_html(self, html, venue_id, event_date):
        """
        Parse HTML and extract all race information
        """
        soup = BeautifulSoup(html, 'html.parser')
        venue_name = self.venues.get(venue_id, f"Unknown Venue ({venue_id})")
        
        # Find all race sections
        race_sections = soup.find_all('div', id=re.compile(r'^race-\d+$'))
        
        if not race_sections:
            return None
        
        races = []
        
        for race_section in race_sections:
            race_data = {}
            
            # Extract race header
            race_header = race_section.find('div', class_='heading_div')
            if not race_header:
                continue
            
            # Basic race info
            race_num_elem = race_header.find('div', class_='side_num')
            race_number = race_num_elem.h1.text.strip() if race_num_elem else "Unknown"
            
            center_heading = race_header.find('div', class_='center_heading')
            race_title = center_heading.h2.text.strip() if center_heading.h2 else "Unknown"
            race_class = center_heading.h3.text.strip() if center_heading.h3 else "Unknown"
            
            archive_time = race_header.find('div', class_='archive_time')
            distance = archive_time.find_all('h4')[0].text.strip() if archive_time else "Unknown"
            time = archive_time.find_all('h4')[1].text.strip() if archive_time and len(archive_time.find_all('h4')) > 1 else "Unknown"
            
            race_data.update({
                'race_number': race_number,
                'title': race_title,
                'class': race_class,
                'distance': distance,
                'time': time,
                'venue': venue_name,
                'venue_id': venue_id,
                'date': event_date
            })
            
            # Extract prize money
            self._extract_prize_money(race_section, race_data)
            
            # Extract record time
            self._extract_record_time(race_section, race_data)
            
            # Extract horse data
            horses = self._extract_horse_data(race_section)
            race_data['horses'] = horses
            self.total_horses_scraped += len(horses)
            
            races.append(race_data)
        
        self.total_races_scraped += len(races)
        
        return {
            'venue': venue_name,
            'venue_id': venue_id,
            'date': event_date,
            'races': races,
            'race_count': len(races)
        }
    
    def _extract_prize_money(self, race_section, race_data):
        """Extract prize money information"""
        prize_section = race_section.find('div', class_='winner_amount')
        if prize_section:
            prize_text = prize_section.find('p', class_='winner_content').text.strip()
            prize_pattern = r"Winner:₹\.([\d,]+)\s+Second:₹\.([\d,]+)\s+Third:₹\.([\d,]+)\s+Fourth:₹\.([\d,]+)\s+Total:₹\.([\d,]+)"
            prize_match = re.search(prize_pattern, prize_text)
            
            if prize_match:
                race_data['prizes'] = {
                    'winner': prize_match.group(1),
                    'second': prize_match.group(2),
                    'third': prize_match.group(3),
                    'fourth': prize_match.group(4),
                    'total': prize_match.group(5)
                }
    
    def _extract_record_time(self, race_section, race_data):
        """Extract track record information"""
        record_section = race_section.find('div', class_='record_time')
        if record_section:
            record_text = record_section.text.strip()
            record_pattern = r"Record Time : (.+) (.+)"
            record_match = re.search(record_pattern, record_text)
            
            if record_match:
                race_data['record'] = {
                    'date': record_match.group(1),
                    'details': record_match.group(2)
                }
    
    def _extract_horse_data(self, race_section):
        """Extract detailed horse information"""
        horses = []
        horse_table = race_section.find('table', class_='race_card_tab')
        
        if not horse_table:
            return horses
        
        for row in horse_table.find('tbody').find_all('tr'):
            horse_data = {}
            cells = row.find_all('td')
            
            if len(cells) < 12:
                continue
            
            # Horse number and draw
            number_cell = cells[0]
            horse_number = number_cell.contents[0].strip() if number_cell.contents else "Unknown"
            draw_number = None
            draw_elem = number_cell.find('span')
            if draw_elem:
                draw_number = draw_elem.text.strip()
            
            horse_data.update({
                'number': horse_number,
                'draw': draw_number
            })
            
            # Silk image
            silk_img = cells[1].find('div', class_='card_tb_image').find('img')
            horse_data['silk'] = silk_img['src'] if silk_img else None
            
            # Horse details
            horse_cell = cells[2]
            if horse_cell:
                horse_name_elem = horse_cell.find('h5').find('a')
                horse_name = horse_name_elem.text.strip() if horse_name_elem else "Unknown"
                horse_link = horse_name_elem['href'] if horse_name_elem else None
                
                horse_data.update({
                    'name': horse_name,
                    'link': urljoin(self.base_url, horse_link) if horse_link else None
                })
                
                # Ex-Name
                ex_name_elem = horse_cell.find('span', style="color:red;font-size:11px;")
                horse_data['ex_name'] = ex_name_elem.text.strip() if ex_name_elem else None
                
                # Pedigree
                pedigree_elem = horse_cell.find('h6', class_='margin_remove')
                horse_data['pedigree'] = pedigree_elem.text.strip() if pedigree_elem else "Unknown"
                
                # Last 5 runs
                last_runs_elem = horse_cell.find('span', class_='last-five-runs-lable')
                horse_data['last_5_runs'] = last_runs_elem.text.strip() if last_runs_elem else None
            
            # Description, Owner, Trainer, Jockey
            horse_data.update({
                'description': cells[3].text.strip(),
                'owner': cells[4].text.strip(),
            })
            
            # Trainer
            trainer_elem = cells[5].find('a')
            horse_data['trainer'] = trainer_elem.text.strip() if trainer_elem else "Unknown"
            trainer_link = trainer_elem['href'] if trainer_elem else None
            horse_data['trainer_link'] = urljoin(self.base_url, trainer_link) if trainer_link else None
            
            # Jockey
            jockey_elem = cells[6].find('a')
            horse_data['jockey'] = jockey_elem.text.strip() if jockey_elem else "Unknown"
            jockey_link = jockey_elem['href'] if jockey_elem else None
            horse_data['jockey_link'] = urljoin(self.base_url, jockey_link) if jockey_link else None
            
            # Weight
            horse_data['weight'] = cells[7].text.strip()
            
            # Equipment
            horse_data['equipment'] = {
                'al': cells[8].text.strip(),
                'sh': cells[9].text.strip(),
                'eq': cells[10].text.strip()
            }
            
            # Rating with penalty
            rating_text = cells[11].text.strip()
            rating_match = re.search(r'<sup><small>(\d+)</small></sup>(\d+)', str(cells[11]))
            if rating_match:
                horse_data['rating'] = rating_match.group(2)
                horse_data['penalty'] = rating_match.group(1)
            else:
                horse_data['rating'] = rating_text
                horse_data['penalty'] = None
            
            horses.append(horse_data)
        
        return horses
    
    def scrape_month(self, year, month, venues=None, race_types=None):
        """
        Scrape all races for a specific month
        """
        if venues is None:
            venues = list(self.venues.keys())
        
        if race_types is None:
            race_types = ["RACECARD"]
        
        # Calculate date range for month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        print(f"Scraping {start_date.strftime('%B %Y')}...")
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        print(f"Venues: {[self.venues[v] for v in venues]}")
        print("-" * 50)
        
        all_data = []
        current_date = start_date
        day_count = 0
        
        while current_date <= end_date:
            day_count += 1
            date_str = current_date.strftime("%Y-%m-%d")
            day_data = {
                'date': date_str,
                'weekday': current_date.strftime("%A"),
                'venues': []
            }
            
            print(f"\nDay {day_count}: {current_date.strftime('%d %B %Y')} ({current_date.strftime('%A')})")
            
            for venue_id in venues:
                venue_name = self.venues.get(venue_id, f"Unknown ({venue_id})")
                print(f"  Scraping {venue_name}...", end="")
                
                venue_data = None
                for race_type in race_types:
                    race_data = self.fetch_race_data(venue_id, date_str, race_type)
                    if race_data:
                        venue_data = race_data
                        print(f" ✓ {len(race_data['races'])} races")
                        break
                    else:
                        print(" ✗ No data", end="")
                
                if venue_data:
                    day_data['venues'].append(venue_data)
                
                # Rate limiting
                time.sleep(0.3)
            
            all_data.append(day_data)
            current_date += timedelta(days=1)
        
        # Generate summary
        summary = {
            'month': f"{year}-{month:02d}",
            'month_name': start_date.strftime("%B %Y"),
            'total_days': day_count,
            'venues_scraped': [self.venues[v] for v in venues],
            'race_types': race_types,
            'total_races': self.total_races_scraped,
            'total_horses': self.total_horses_scraped,
            'failed_requests': self.failed_requests,
            'data': all_data
        }
        
        return summary
    
    def save_monthly_data(self, data, output_dir="indiarace_monthly"):
        """
        Save monthly data in multiple formats
        """
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        month_str = data['month']
        
        # Save complete JSON
        json_file = os.path.join(output_dir, f"indiarace_{month_str}_complete.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Complete data saved to: {json_file}")
        
        # Save races-only JSON (flattened)
        races_file = os.path.join(output_dir, f"indiarace_{month_str}_races.json")
        all_races = []
        for day_data in data['data']:
            for venue_data in day_data['venues']:
                if venue_data and 'races' in venue_data:
                    all_races.extend(venue_data['races'])
        
        with open(races_file, 'w', encoding='utf-8') as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        print(f"✓ Races data saved to: {races_file}")
        
        # Save CSV
        csv_file = os.path.join(output_dir, f"indiarace_{month_str}.csv")
        self._save_to_csv(all_races, csv_file)
        print(f"✓ CSV data saved to: {csv_file}")
        
        # Save summary
        summary_file = os.path.join(output_dir, f"indiarace_{month_str}_summary.txt")
        self._save_summary(data, summary_file)
        print(f"✓ Summary saved to: {summary_file}")
    
    def _save_to_csv(self, races, filename):
        """Save race data to CSV format"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            header = [
                'Date', 'Weekday', 'Venue', 'Race Number', 'Title', 'Class',
                'Distance', 'Time', 'Horse Number', 'Draw', 'Horse Name',
                'Ex-Name', 'Pedigree', 'Last 5 Runs', 'Description',
                'Owner', 'Trainer', 'Jockey', 'Weight', 'AL', 'SH', 'EQ',
                'Rating', 'Penalty', 'Prize Winner', 'Prize Second',
                'Prize Third', 'Prize Fourth', 'Prize Total'
            ]
            writer.writerow(header)
            
            # Write data
            for race in races:
                for horse in race.get('horses', []):
                    row = [
                        race.get('date', ''),
                        race.get('date', ''),  # Will be updated by caller if needed
                        race.get('venue', ''),
                        race.get('race_number', ''),
                        race.get('title', ''),
                        race.get('class', ''),
                        race.get('distance', ''),
                        race.get('time', ''),
                        horse.get('number', ''),
                        horse.get('draw', ''),
                        horse.get('name', ''),
                        horse.get('ex_name', ''),
                        horse.get('pedigree', ''),
                        horse.get('last_5_runs', ''),
                        horse.get('description', ''),
                        horse.get('owner', ''),
                        horse.get('trainer', ''),
                        horse.get('jockey', ''),
                        horse.get('weight', ''),
                        horse.get('equipment', {}).get('al', ''),
                        horse.get('equipment', {}).get('sh', ''),
                        horse.get('equipment', {}).get('eq', ''),
                        horse.get('rating', ''),
                        horse.get('penalty', ''),
                        race.get('prizes', {}).get('winner', ''),
                        race.get('prizes', {}).get('second', ''),
                        race.get('prizes', {}).get('third', ''),
                        race.get('prizes', {}).get('fourth', ''),
                        race.get('prizes', {}).get('total', '')
                    ]
                    writer.writerow(row)
    
    def _save_summary(self, data, filename):
        """Save scraping summary to text file"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"INDIARACE MONTHLY SCRAPING SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Month: {data['month_name']}\n")
            f.write(f"Total Days: {data['total_days']}\n")
            f.write(f"Venues Scraped: {', '.join(data['venues_scraped'])}\n")
            f.write(f"Race Types: {', '.join(data['race_types'])}\n")
            f.write(f"Total Races Found: {data['total_races']}\n")
            f.write(f"Total Horses Found: {data['total_horses']}\n")
            f.write(f"Failed Requests: {data['failed_requests']}\n\n")
            
            # Daily breakdown
            f.write("DAILY BREAKDOWN:\n")
            f.write("-" * 30 + "\n")
            for day_data in data['data']:
                total_races = sum(len(v.get('races', [])) for v in day_data['venues'])
                f.write(f"{day_data['date']} ({day_data['weekday']}): {total_races} races\n")
    
    def print_final_stats(self, data):
        """Print final scraping statistics"""
        # Calculate success rate separately to avoid f-string complexity
        total_requests = data['total_days'] * len(data['venues_scraped'])
        successful_requests = total_requests - data['failed_requests']
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        print("\n" + "=" * 50)
        print("SCRAPING COMPLETED")
        print("=" * 50)
        print(f"Month: {data['month_name']}")
        print(f"Total Days Processed: {data['total_days']}")
        print(f"Total Races Scraped: {data['total_races']}")
        print(f"Total Horses Scraped: {data['total_horses']}")
        print(f"Failed Requests: {data['failed_requests']}")
        print(f"Success Rate: {success_rate:.1f}%")
        print("=" * 50)


# Example usage
if __name__ == "__main__":
    scraper = IndiaraceMonthlyScraper()
    
    # Get current month data
    now = datetime.now()
    year = now.year
    month = now.month
    
    # Or specify a different month
    # year = 2025
    # month = 12
    
    print(f"Starting scrape for {year}-{month:02d}")
    
    # Scrape all venues for the month
    monthly_data = scraper.scrape_month(
        year=year,
        month=month,
        venues=list(scraper.venues.keys()),  # All venues
        race_types=["RACECARD"]  # Race cards only
    )
    
    # Save all data
    scraper.save_monthly_data(monthly_data)
    
    # Print final statistics
    scraper.print_final_stats(monthly_data)
    
    # Example: Scrape only specific venues
    # specific_venues = [1, 2, 3]  # Mumbai, Kolkata, Bangalore
    # specific_data = scraper.scrape_month(year, month, venues=specific_venues)
    # scraper.save_monthly_data(specific_data, output_dir="indiarace_specific_venues")