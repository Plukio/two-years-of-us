import streamlit as st
from streamlit_timeline import timeline
import json
import datetime
import boto3
from botocore.exceptions import NoCredentialsError
from datetime import date
import gspread
from google.oauth2 import service_account


# AWS S3 Configuration

# Initialize S3 client
s3 = boto3.client("s3", aws_access_key_id=st.secrets["AWS_ACCESS_KEY"], aws_secret_access_key=st.secrets["AWS_SECRET_KEY"])

# Google Sheets Configuration
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "TimelineEvents"

# Authenticate and open Google Sheet
credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPE)

client = gspread.authorize(credentials)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1dpPFk7gXnlOp-Y_6N0mAjUp1bpkXAf7AjER1ry3DqCs/edit?usp=sharing").sheet1

# Configure Streamlit
st.set_page_config(page_title="Timeline Example", layout="wide")

# Initialize timeline data
timeline_data = {
    "title": {
        "media": {
            "url": "",
            "caption": "<a target='_blank' href=''>credits</a>",
            "credit": ""
        },
        "text": {
            "headline": "Welcome to<br>Our Lovely Memories!",
            "text": "<p>Two years of tears and joy, every moment bringing us closer to this beautiful chapter...</p>"
        }
    },
    "events": []
}

# Load all unique tags and existing events from Google Sheets
all_tags = set()
try:
    all_records = sheet.get_all_values()
    for record in all_records:  # Skip header
        tag = record[7]  # Assuming tag column is at index 7
        all_tags.add(tag)

        event = {
            "media": {
                "url": record[2],
                "caption": record[3]
            },
            "start_date": {
                "year": record[4],
                "month": record[5],
                "day": record[6]
            },
            "text": {
                "headline": record[0],
                "text": record[1]
            },
            "tag": tag
        }
        timeline_data["events"].append(event)
except Exception as e:
    st.error(f"Error loading data from Google Sheets: {e}")

# Sidebar form to add new events
with st.sidebar.form(key="add_event_form"):
    event_headline = st.text_input("Event Headline", "Event Title")
    event_text = st.text_area("Event Text", "Event Description")
    
    # Image upload
    uploaded_file = st.file_uploader("Upload an Image", type=["jpg", "jpeg", "png", "heic"])
    event_caption = st.text_input("Media Caption", "Image Caption")
    
    # Date picker for start date
    start_date = st.date_input("Start Date", datetime.datetime.now())
    
    # Tag selection: choose from existing tags or add a new one
    existing_tags = list(all_tags)
    new_tag = st.text_input("New Tag (or select from existing)")
    tag = st.selectbox("Select Tag", options=[""] + existing_tags)
    chosen_tag = new_tag if new_tag else tag
    
    submit_button = st.form_submit_button("Add Event")

    # Add event to S3 and Google Sheets if the form is submitted
    if submit_button and uploaded_file is not None and chosen_tag:
        try:
            # Upload image to S3
            s3_filename = f"timeline_images/{uploaded_file.name}"
            s3.upload_fileobj(uploaded_file, st.secrets["BUCKET_NAME"], s3_filename, ExtraArgs={"ACL": "public-read", "ContentType": uploaded_file.type})
            
            # Get the image URL
            image_url = f"https://{st.secrets["BUCKET_NAME"]}.s3.amazonaws.com/{s3_filename}"

            # Prepare new event data
            new_event = {
                "Event Headline": event_headline,
                "Event Text": event_text,
                "Image URL": image_url,
                "Media Caption": event_caption,
                "Year": str(start_date.year),
                "Month": str(start_date.month),
                "Day": str(start_date.day),
                "Tag": chosen_tag
            }
            
            # Add event to Google Sheets
            sheet.append_row([new_event[key] for key in new_event.keys()])

            # Append to local timeline data
            timeline_data["events"].append({
                "media": {
                    "url": image_url,
                    "caption": event_caption
                },
                "start_date": {
                    "year": str(start_date.year),
                    "month": str(start_date.month),
                    "day": str(start_date.day)
                },
                "text": {
                    "headline": event_headline,
                    "text": event_text
                },
                "tag": chosen_tag
            })
            
            # Update tags set
            all_tags.add(chosen_tag)
            st.success("Event added successfully!")

        except NoCredentialsError:
            st.error("Credentials not available for S3 upload. Check your AWS access key and secret key.")
        except Exception as e:
            st.error(f"Error adding event: {e}")

# Filter events by selected tag




with st.popover("Filter Event"):
    selected_tag = st.multiselect(
    "Select Tags to Filter Event",
    list(all_tags) + ["All"],
    ["All"])
    
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

def get_event_date(event_date):
    return date(int(event_date["year"]), int(event_date["month"]), int(event_date["day"]))

# Filter events based on tags and date range
filtered_events = []
if "All" in selected_tag:
    # Apply date filter only
    filtered_events = [
        event for event in timeline_data["events"]
        if start_date <= get_event_date(event["start_date"]) <= end_date
    ]
else:
    # Apply both tag and date filters
    filtered_events = [
        event for event in timeline_data["events"]
        if event.get("tag") in selected_tag and start_date <= get_event_date(event["start_date"]) <= end_date
    ]
    
# Convert filtered data to JSON format for timeline rendering
filtered_timeline_data = {
    "title": timeline_data["title"],
    "events": filtered_events
}

timeline_data_json = json.dumps(filtered_timeline_data)

# Display the filtered timeline

timeline(timeline_data_json, height=500)
