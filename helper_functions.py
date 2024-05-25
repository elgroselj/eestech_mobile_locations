import osmnx as osm

def load_json_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def list_in_bin_at_time(lat_min,lat_max,lon_min,lon_max,time_mode="podnevi",
                        index="geo-locations-12.01.2023", 
                        sample_size=9000,
                        tresh= 1,
                        potrpezljivost_limit=200_000):

    assert time_mode in ["ponoci", "podnevi"]
    
    # date
    M,D,Y = list(map(int,index[-10:].split(".")))
    datum = "{}-{:02d}-{:02d}".format(Y,D,M)
    
    search_query = {
        "query": {
        "bool": {
            "filter": [
            {
                "geo_bounding_box": {
                "location": {
                    "top_left": {"lat": lat_max, "lon": lon_min},
                    "bottom_right": {"lat": lat_min, "lon": lon_max}
                }
                }
            }
            ,
            {
                "range": {
                    "dateTimeEvent": {
                    # podnevi := kje is med 10h in 13h
                    # ponoci := kje si med 20h in 22h
                    "gte": datum+"T20:00:00"\
                        if time_mode == "ponoci" else datum+"T10:00:00" ,
                    "lte": datum+"T22:00:00"\
                        if time_mode == "ponoci" else datum+"T13:00:00"
                    }
                }
            }
            ]
        }
        },
        "_source": ["msisdn"],
        "size": sample_size
    }
    
    d = {}
    st = 0

    response = es.search(index=index,
                        body=json.dumps(search_query),
                        scroll='1m') # 1 minuta
    
    scroll_id = response['_scroll_id']
    
    while len(response['hits']['hits']):
        st += 1        
        for hit in response['hits']['hits']:
            # msisdn := id uporabnika
            # stejemo ponovitve uporabnikov
            if hit['_source']["msisdn"] in d.keys():
                d[hit['_source']["msisdn"]] += 1
            else:
                d[hit['_source']["msisdn"]] = 1
                
        print(len(d))
        if st % 10 == 0:
            s = []
            for k in d.keys():
                if d[k] > tresh:
                    s.append(k)
                    
            print("s_len",len(s))
            if len(s) > potrpezljivost_limit:
                break
        
        # Make a request using the Scroll API
        response = es.scroll(
            scroll_id=scroll_id,
            scroll='1m'  # Extend the scroll window for another minute
        )

        # Update the scroll ID
        scroll_id = response['_scroll_id']

    # Clear the scroll when you're done
    es.clear_scroll(scroll_id=scroll_id)
    
    # sestavi seznam uporabnikov, ki se zadostikrat ponovijo
    s = []
    for k in d.keys():
        if d[k] > tresh:
            s.append(k)
            
    print("s_len",len(s))
    return s

def read_file(filename):
    with open(filename, 'r') as file:
        return set(file.read().splitlines(", "))

def find_common_strings(file1, file2):
    presek = []
    with open(file1) as f1:
        with open(file2) as f2:
            for id1 in f1.read().strip("[]").split(",").strip("'"):
                for id2 in f2.read().strip("[]").split(", ").strip("'"):
                    if id1 == id2:
                        presek.append(id1)
    
    return presek


def ime_to_lat_lon(ime):
    try:
        feat = osm.features.features_from_address(ime, tags={'highway':'bus_stop'}, dist=1000)
        is_bus_stop = "bus_stop" in np.array(feat["highway"])
    except Exception:
        return (None,None), None
    return osm.geocoder.geocode(ime), is_bus_stop

    
# ime_to_lat_lon("Trzin Mlake krizisce")
      
def dateTime_to_hours(dt):
    h,m = map(int, dt[-5:].split(":"))
    return h+m/60


def visualize(id,stops=[]):
    # prikaže vse lokacije enega uporabnika in morebitne (podane) postanke avtobusa
    search_query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"msisdn": id}}
                ]
            }
        },
        "size": 9000,
    }

    # Execute the search query
    response = es.search(
        index="geo-locations-12.01.2023", body=json.dumps(search_query)
    )

    # Print the search results
    r = []
    s = set()
    for hit in response["hits"]["hits"]:
        r.append(hit["_source"])
        s.add(str(hit["_source"]["location"]))
    print(len(r))

    m = folium.Map(
        [46.0575677, 14.8314192],
        zoom_start=10.6
    )

    for e in r:
        t = e["dateTimeEvent"]
        c = [(8,"green"),(13,"beige"),(18,"orange"),(24,"red")]
        
        def get_color(t):
            time = dateTime_to_hours(t)
            for h, col in c:
                if time < h:
                    return col
            return "blue"
                
        loc = e["location"]
        lat1 = loc["lat"]
        lon1 = loc["lon"]

        folium.Marker(
            location=[lat1, lon1],
            icon=folium.Icon(icon="cloud",color=get_color(t)), 
            tooltip=t, popup=t,            
        ).add_to(m)
        
    for e in stops:
        t, lat1, lon1 = e
        folium.Marker(
            location=[lat1, lon1],
            icon=folium.Icon(icon="cloud",color="black"),
            tooltip=t, 
            popup=t,
        ).add_to(m)
    return m, r


def cuts(lat_min, lat_max, lon_min, lon_max, id, mode="101",r=None):
    # najde prve točke, naprava zapustila/prispela v kraj
    # 010 (1.. = naš kraj,  0.. = ne naš kraj)
    if r is None:
        _, r = visualize(id)
    data = [
        (
            dateTime_to_hours(e["dateTimeEvent"]),
            e["location"]["lat"],
            e["location"]["lon"],
        )
        for e in r
    ]
    data = np.array(data)

    df = pd.DataFrame(data, columns=["time", "lat", "lon"])

    df = df.sort_values(by=["time"])
    df = df[
        (lat_min < df["lat"])
        & (lat_max > df["lat"])
        & (lon_min < df["lon"])
        & (lon_max > df["lon"])
    ].reset_index()
    
    if mode == "101":
        max_diff = 0
        max_i = 0
        for i in range(1, len(df)):
            diff = abs(df.loc[i - 1]["time"] - df.loc[i]["time"])
            if diff > max_diff:
                max_diff = diff
                max_i = i
        return df.loc[max_i - 1]["time"], df.loc[max_i]["time"]
    
    elif mode == "010":
        return df.loc[0]["time"], df.loc[len(df) - 1]["time"]
    

def RANSAC(points,field="lat",plot=True):
    if len(points) == 0:
        return None
    
    X = np.array(points["time"]).reshape(-1,1)
    y = np.array(points[field]).reshape(-1,1)
    
    plt.scatter(np.array(points["time"]),points[field])
    plt.show()

    # Fit line using all data
    lr = linear_model.LinearRegression()
    lr.fit(X, y)

    # Robustly fit linear model with RANSAC algorithm
    ransac = linear_model.RANSACRegressor()
    ransac.fit(X, y)
    inlier_mask = ransac.inlier_mask_
    outlier_mask = np.logical_not(inlier_mask)

    # Predict data of estimated models
    line_X = np.arange(X.min(), X.max(),0.1)[:, np.newaxis]
    line_y = lr.predict(line_X)
    line_y_ransac = ransac.predict(line_X)

    if plot:
        lw = 2
        plt.scatter(
            X[inlier_mask], y[inlier_mask], color="yellowgreen", marker=".", label="Inliers"
        )
        plt.scatter(
            X[outlier_mask], y[outlier_mask], color="gold", marker=".", label="Outliers"
        )
        plt.plot(
            line_X,
            line_y_ransac,
            color="cornflowerblue",
            linewidth=lw,
            label="RANSAC regressor",
        )
        
    x1 = line_X[0]
    x2 = line_X[-1]
    y1 = line_y_ransac[0]
    y2 = line_y_ransac[-1]

    # utežimo lat in lon
    # k predstavlja hitrost v lat oz. lon smeri
    k = (y2-y1)/(x2-x1)
    if field == "lat":
        # 1 dec deg = 110754.3 m = 110.7543 km
        k = 110.7543 * k
    elif field == "lon":
        k = 77 * k
        
    return k

