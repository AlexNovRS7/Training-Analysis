import requests
import json
import pandas as pd
import numpy as np
import time
from datetime import date
import csv
import json
from dateutil import parser

import garminconnect


with open('secrets.json') as secrets_file:
    parsed_json = json.load(secrets_file)
    login = parsed_json["GARMIN_LOGIN"]
    password = parsed_json["GARMIN_PASS"]

garmin = garminconnect.Garmin(login, password)
garmin.login()


garmin_activities = garmin.get_activities_by_date("2023-01-01", date.today().isoformat())

print(len(garmin_activities))