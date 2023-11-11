import requests
import json
import pandas as pd
import numpy as np
import time
import datetime
import csv
import json
from dateutil import parser

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def refresh_token(old_refresh_token):
    response = requests.post(
        url = 'https://www.strava.com/oauth/token',
        data = {'client_id':CLIENT_ID,
                'client_secret':"9859ded508278dfbcf717854a3636bdb396ed6bb",
                'refresh_token':old_refresh_token,
                'grant_type':'refresh_token'})
    json_response = json.loads(response.text)
    try:
        REFRESH_TOKEN = json_response["refresh_token"]
        ACCESS_TOKEN = json_response["access_token"]

        data = {
            "REFRESH_TOKEN": REFRESH_TOKEN,
            "CLIENT_ID": CLIENT_ID,
            "ACCESS_TOKEN": ACCESS_TOKEN
        }
        with open('secrets.json', 'w') as f:
            json.dump(data, f)

    except:
        print("Something is wrong, go get new code again")


def get_all_cycling_activities(access_token, after):
    logging.info("started loading activities")
    base_url = "https://www.strava.com/api/v3/athlete/activities"
    page = 1
    per_page = 30  # Adjust as needed

    all_activities = []

    while True:
        params = {"type": "Ride", "page": page, "per_page": per_page, "after": after}
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break

        activities = response.json()

        # Process the activities here, e.g., store them in a list
        all_activities.extend(activities)

        # Check if there are more pages
        if len(activities) < per_page:
            break

        page += 1

    return all_activities


def save_to_csv(data, filename):
    if not data:
        print("No data to save.")
        return
    
    # Extract all unique keys from all activities
    fields = set().union(*(d.keys() for d in data))
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        
        # Write the header
        writer.writeheader()
        
        # Write the data
        writer.writerows(data)


def get_power_stream(activity_id):
    while True:
        stream_response = session.get(f"https://www.strava.com/api/v3/activities/{activity_id}/streams/watts?access_token={ACCESS_TOKEN}") 
        stream_json = json.loads(stream_response.text)
        for stream in stream_json:
            try:
                if stream["type"] == "watts":
                    return stream["data"]
            except TypeError:
                print("Rate limit exceeded, waiting for a minute")
                print(stream_response.text)
                time.sleep(60)


def calculate_np(power_stream):
    watts_df = pd.DataFrame(power_stream, columns=["Wats"])
    watts_df["30s rolling w"] = watts_df["Wats"].rolling(30, 0).mean() ** 4

    avg_powered_values = watts_df["30s rolling w"].mean()
    return avg_powered_values ** 0.25


with open('secrets.json') as secrets_file:
    parsed_json = json.load(secrets_file)
    CLIENT_ID = parsed_json["CLIENT_ID"]
    REFRESH_TOKEN = parsed_json["REFRESH_TOKEN"]
    ACCESS_TOKEN = parsed_json["ACCESS_TOKEN"]


# open downloaded activities
with open('activities.json') as activities_file:
    all_cycling_activities = json.load(activities_file)
logging.info(f"Opened {len(all_cycling_activities)} existing activities")


# check last activity epoch
last_epoch = max([parser.parse(activity["start_date"]).timestamp() for activity in all_cycling_activities])

session = requests.Session()

new_cycling_activities = get_all_cycling_activities(ACCESS_TOKEN, last_epoch)
logging.info(f"Downloaded {len(new_cycling_activities)} new activities")

all_cycling_activities.extend(new_cycling_activities)
logging.info(f"Stacked both files. Activities in sum {len(all_cycling_activities)}")

# download power streams
#TODO

df = pd.DataFrame(all_cycling_activities)
df = df.loc[(df["type"].str.contains("Ride"))]
df["start_date"] = pd.to_datetime(df["start_date"])
df["start_date"] = df["start_date"].dt.tz_localize(None).dt.date
df.sort_values("start_date", inplace=True)

ftp_df = pd.read_csv('ATP - FTP.csv')
ftp_df["Date"] = pd.to_datetime(ftp_df["Date"], format="%d/%m/%Y").dt.date
logging.info("FTP file loaded")

df = df.merge(ftp_df[["Date", "Power"]], how='left', left_on='start_date', right_on='Date')
df["FTP set"] = df["Power"].ffill()
df.drop(["Date", "Power"], axis=1, inplace=True)
logging.info("Activities and FTP dataframes merged")

df["NP"] = df["power stream"].apply(lambda x: calculate_np(x))
logging.info("NP calculated")

df["IF"] = df["NP"]/df["FTP set"]
logging.info("IF calculated")

df["TSS"] = ((df["moving_time"] * df["NP"] * df["IF"]) / (df["FTP set"]*3600)) * 100
logging.info("TSS calculated")

df["CTL"] = df["TSS"].rolling(42,0).mean().shift(1)
logging.info("CTL calculated")

df["ATL"] = df["TSS"].rolling(77,0).mean().shift(1)
logging.info("ATL calculated")

df["TSB"] = df["CTL"] - df["ATL"]
logging.info("TSB calculated")

save_to_csv(df, 'cycling_activities.csv')
