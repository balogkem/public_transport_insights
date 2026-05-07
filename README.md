# public_transport_insights

A Flask-based dashboard for analyzing public transport performance data, focusing on route delays, passenger load, and weather impacts.

## Features

- **Route Delays Analysis**: Identify routes most susceptible to delays, with congestion zone comparisons.
- **Passenger Load Insights**: Correlate passenger capacity utilization with trip durations and overruns.
- **Weather Impact**: Analyze how weather conditions affect route performance.
- **Interactive Dashboard**: Built with Plotly.js for dynamic charts and visualizations.

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL database (or Supabase)

### Installation

1. **Clone the repository** (if not already done).

2. **Set up a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Set up the database**:
   - Create a PostgreSQL database.
   - Ensure the following tables exist (based on the queries in `app.py`):
     - `Route` (route_id, route_name, passes_congestion_zone)
     - `Trip` (trip_id, route_id, delay_mins, actual_duration_mins, scheduled_duration_mins, scheduled_departure, weather_id)
     - `Passenger_Record` (trip_id, capacity_utilisation_pct, peak_count, overcrowding_flag)
     - `Weather_Condition` (weather_id, condition_label, rainfall_mm, temperature_c)
   - Populate with sample data or connect to your data source.

5. **Configure environment variables**:
   ```bash
   cd backend
   cp .env.example .env
   ```
   Edit `.env` and set your `DATABASE_URL`:
   ```
   DATABASE_URL=postgresql://username:password@host:port/database
   ```

### Running the Application

1. **Start the Flask server**:
   ```bash
   cd backend
   python app.py
   ```
   The app will run on `http://localhost:5000`.

2. **Open the dashboard**:
   - Visit `http://localhost:5000` in your browser.
   - The frontend is served by Flask and will fetch data from the API endpoints.

### API Endpoints

- `/api/status`: Health check for database connection.
- `/api/hero`: Summary stats for the hero banner.
- `/api/routes/delays`: Route delay analysis.
- `/api/routes/delay-distribution`: Delay distribution histogram.
- `/api/passengers/scatter`: Passenger count vs delay scatter plot.
- `/api/passengers/overrun-by-bracket`: Overrun by capacity bracket.
- `/api/passengers/peak-hours`: Overcrowded trips by hour.
- `/api/weather/delays`: Weather conditions vs delays.
- `/api/weather/rainfall-scatter`: Rainfall vs delay scatter.

## Project Structure

```
public_transport_insights/
├── README.md
├── backend/
│   ├── app.py          # Flask application
│   ├── db.py           # Database connection utilities
│   ├── requirements.txt # Python dependencies
│   └── .env.example    # Environment variables template
└── frontend/
    └── index.html      # Dashboard HTML/JS
```

## Technologies Used

- **Backend**: Flask, PostgreSQL (psycopg2), python-dotenv
- **Frontend**: HTML, CSS, JavaScript, Plotly.js
- **Database**: PostgreSQL

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test thoroughly.
5. Submit a pull request.

## License

This project is for educational/prototype purposes.