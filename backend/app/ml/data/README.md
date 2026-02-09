# Training Data Directory

## 📁 Purpose

This directory stores datasets used for training the Hanco-AI pricing model.

## 📊 Required Dataset

Place your dataset file here:

```
app/ml/data/saudi_car_rental_synthetic.csv
```

## 📋 Expected CSV Format

The dataset should contain the following columns (or columns that can be derived):

### Core Features
- `rental_length_days` - Number of days for the rental
- `day_of_week` - Day of week (0-6, where 0=Monday)
- `month` - Month number (1-12)
- `base_daily_rate` - Base daily rate for the vehicle (SAR)

### Weather Features
- `avg_temp` - Average temperature (°C)
- `rain` - Rainfall amount (mm)
- `wind` - Wind speed (km/h)

### Market Features
- `avg_competitor_price` - Average competitor price (SAR)
- `demand_index` - Demand index (0.0-1.0)

### Target Variable
- `daily_price` - Daily rental price (SAR) **OR**
- `total_price` - Total rental price (SAR) + `rental_length_days` to calculate daily price

### Optional Columns
- `city` - City name (e.g., "Riyadh", "Jeddah")
- `category` - Vehicle category (e.g., "Economy", "Luxury")
- `vehicle_id` - Unique vehicle identifier
- `booking_id` - Unique booking identifier

## 🔧 Data Preprocessing

The training script (`train_pricing_model.py`) will automatically:

1. **Convert total_price to daily_price** if needed
2. **Add bias column** (constant 1.0)
3. **Fill missing values** with medians
4. **Validate data quality** before training

## 🚀 Usage

Once your dataset is in place, run:

```bash
cd backend
python app/ml/training/train_pricing_model.py
```

The script will:
- Load and validate the dataset
- Train a GradientBoostingRegressor
- Export to ONNX format
- Save trained model to `app/ml/models/model.onnx`

## 📌 Notes

- **Do NOT commit large CSV files** to version control
- Add `*.csv` to `.gitignore` if storing real customer data
- The trained ONNX model will automatically be used by the pricing API
- No code changes needed - just restart the server after training
