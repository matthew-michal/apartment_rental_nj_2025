import requests
import json
import pandas as pd
import pickle
import os

# url = "https://api.rentcast.io/v1/listings/rental/long-term?state=NJ&status=Active&limit=500&offset=500"
# url = "https://api.rentcast.io/v1/listings/rental/long-term?latitude=40.79756715723661&longitude=-74.47460155149217&radius=1&status=Active&limit=500"
# url = "https://api.rentcast.io/v1/listings/rental/long-term?latitude=40.79572107840714&longitude=-74.363299819611&radius=7&status=Active&limit=500"
url = "https://api.rentcast.io/v1/listings/rental/long-term?latitude=40.8314005740992&longitude=-74.40197132373629&radius=12&status=Active&limit=500"
# url = "https://api.rentcast.io/v1/listings/rental/long-term?latitude=40.8314005740992&longitude=-74.40197132373629&radius=12&limit=500"

API_KEY = os.getenv('API_KEY')
headers = {
    "accept": "application/json",
    "X-Api-Key": API_KEY,
    "X-API-Key": API_KEY   
}

def find_df(url, run=0):
    if run != 0:
        print(run)
        url += f'&offset={500*run}'

    response = requests.get(url, headers=headers)

    # print(response.text)

    with open('data.bin','wb') as f_out:
        pickle.dump(response, f_out)

    filtered_data = [{k: v for k, v in item.items() if k != "history"} for item in json.loads(response.text)]

    # df = pd.DataFrame([filtered_data])
    df = pd.DataFrame(filtered_data)
    return df

def data_pull():
    runs = 0
    df = find_df(url,run=runs)
    df_total = df.copy()

    while df.shape[0] == 500:
        runs += 1
        df = find_df(url,run=runs)
        df_total = pd.concat([df_total, df])

        if runs == 15:
            break

    return df_total

def data_pull(api_key=None):
    # Use passed API key or fall back to environment variable
    if api_key:
        API_KEY = api_key
    else:
        API_KEY = os.getenv('API_KEY')
    
    
    # Update headers with the actual API key
    headers = {
        "accept": "application/json",
        "X-Api-Key": API_KEY
    }
    
    # Update find_df to use the local headers
    def find_df_local(url, run=0):
        if run != 0:
            print(run)
            url += f'&offset={500*run}'

        response = requests.get(url, headers=headers)  

        # Rest of your existing find_df code...
        with open('data.bin','wb') as f_out:
            pickle.dump(response, f_out)

        filtered_data = [{k: v for k, v in item.items() if k != "history"} for item in json.loads(response.text)]
        df = pd.DataFrame(filtered_data)
        return df
    
    runs = 0
    df = find_df_local(url, run=runs)
    df_total = df.copy()

    while df.shape[0] == 500:
        runs += 1
        df = find_df_local(url, run=runs)
        df_total = pd.concat([df_total, df])

        if runs == 15:
            break

    return df_total

if __name__ == '__main__':
    df = data_pull()

    df.to_csv('training_load.csv', index=False)