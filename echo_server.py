import socket
import psycopg2
import sys
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

largest_known_id = 0
selected_rows = []

THREE_HOURS = 3
MINUTES_PER_HOUR = 60
SECONDS_PER_MINUTE = 60
SECONDS_PER_THREE_HOURS = THREE_HOURS * MINUTES_PER_HOUR * SECONDS_PER_MINUTE

VALID_QUERIES = ["What is the average moisture inside my kitchen fridge in the past three hours?",
                 "What is the average water consumption per cycle in my smart dishwasher?",
                 "Which device consumed more electricity among my three IoT devices?"]

FIRST_FRIDGE_ID = "id4-6e4-ls8-f7q"
DISHWASHER_ID = "7pz-ybr-8s0-6h3"
SECOND_FRIDGE_ID = "27a451a2-eac4-471d-8cf7-de13d8900eaf"

# ANSI color codes for terminal output
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

device_name_lookup = { FIRST_FRIDGE_ID: "Kitchen Fridge",
                      DISHWASHER_ID: "Smart Dishwasher",
                      SECOND_FRIDGE_ID: "Second Fridge" }

def liters_to_gallons(liters):
    GALLONS_PER_LITER = 0.264172
    gallons = liters * GALLONS_PER_LITER
    return gallons

def amps_to_kilowatts(amps, volts=120):
    kilowatts = amps * volts / 1000
    return kilowatts

def amps_to_kilowatt_hours(amps, hours, volts=120):
    kilowatts = amps_to_kilowatts(amps, volts)
    kilowatt_hours = kilowatts * hours
    return kilowatt_hours

def seconds_to_hours(seconds):
    MINUTE_PER_SECONDS = 1 / 60
    HOUR_PER_MINUTES = 1 / 60
    HOURS_PER_SECOND = HOUR_PER_MINUTES * MINUTE_PER_SECONDS
    hours = seconds * HOURS_PER_SECOND
    return hours

def payload_timestamp(payload):
    timestamp = payload.get("timestamp")
    if timestamp is None:
        return None

    try:
        timestamp = float(timestamp)
    except (TypeError, ValueError):
        parsed_timestamp = datetime.fromisoformat(str(timestamp))
        if parsed_timestamp.tzinfo is None:
            return parsed_timestamp.replace(tzinfo=timezone.utc)
        return parsed_timestamp.astimezone(timezone.utc)

    if timestamp > 100000000000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, timezone.utc)

def find_measurement(payload, *key_fragments):
    for key, value in payload.items():
        normalized_key = key.casefold()
        if all(fragment.casefold() in normalized_key for fragment in key_fragments):
            return value
    return None

def get_client_requested_data(query_index, cursor):
    global largest_known_id
    global selected_rows
    # Fetches data from Neon database
    cursor.execute(f'select PAYLOAD, ID from "{os.getenv("DATABASE_NAME")}" WHERE ID > %s', (largest_known_id,))
    new_rows = cursor.fetchall()
    selected_rows.extend((row[0], row[1]) for row in new_rows)
    if new_rows:
        largest_known_id = max(largest_known_id, *(row[1] for row in new_rows))

    if query_index == 0:
        moisture_measurements = []
        current_time = datetime.now(timezone.utc)

        for row in selected_rows:
            current_payload = row[0]
            moisture_measurement = find_measurement(current_payload, "moisture")
            current_creation_time = payload_timestamp(current_payload)
            if moisture_measurement is not None and current_creation_time is not None:
                time_diff = (current_time - current_creation_time).total_seconds()
                if time_diff < 0 or time_diff > SECONDS_PER_THREE_HOURS:
                    continue
                moisture_measurement = float(moisture_measurement)
                moisture_measurements.append(moisture_measurement)

        if moisture_measurements:
            average_moisture_inside_first_fridge_in_past_three_hours = sum(moisture_measurements) / len(moisture_measurements)
            client_requested_data = f"Average moisture inside {device_name_lookup[FIRST_FRIDGE_ID]} in the past three hours: {average_moisture_inside_first_fridge_in_past_three_hours:.2f}% Relative Humidity"

        else:
            client_requested_data = f"{device_name_lookup[FIRST_FRIDGE_ID]} did not produce any moisture data within the past three hours"

    elif query_index == 1:
        water_consumption_measurements = []

        for row in selected_rows:
            current_payload = row[0]
            water_consumption_measurement = find_measurement(current_payload, "water", "consumption")
            if water_consumption_measurement is not None:
                water_consumption_measurement = float(water_consumption_measurement)
                water_consumption_measurements.append(water_consumption_measurement)

        if water_consumption_measurements:
            average_water_consumption_per_cycle_in_dishwasher = sum(water_consumption_measurements) / len(water_consumption_measurements)
            client_requested_data = f"Average water consumption per cycle in {device_name_lookup[DISHWASHER_ID]}: {liters_to_gallons(average_water_consumption_per_cycle_in_dishwasher):.2f} gallons per minute"

        else:
            client_requested_data = f"{device_name_lookup[DISHWASHER_ID]} did not produce any water consumption data yet"

    elif query_index == 2:
        electricity_consumption_by_device_id = {}
        start_end_time_by_device_id = {}

        for row in selected_rows:
            current_payload = row[0]
            current_creation_time = payload_timestamp(current_payload)
            if current_creation_time is None:
                continue

            current_device_id = current_payload.get("parent_asset_uid")
            fridge_amps = find_measurement(current_payload, "acs712", "fridge")
            dishwasher_amps = find_measurement(current_payload, "acs712", "dishwasher")
            second_fridge_amps = find_measurement(current_payload, "sensor 1")
            if fridge_amps is not None:
                device_id, current_amps = FIRST_FRIDGE_ID, fridge_amps
            elif dishwasher_amps is not None:
                device_id, current_amps = DISHWASHER_ID, dishwasher_amps
            elif second_fridge_amps is not None or current_device_id == SECOND_FRIDGE_ID:
                if second_fridge_amps is None:
                    continue
                device_id, current_amps = SECOND_FRIDGE_ID, second_fridge_amps
            else:
                continue

            electricity_consumption_by_device_id[device_id] = (
                electricity_consumption_by_device_id.get(device_id, 0) + float(current_amps)
            )
            start_time, end_time = start_end_time_by_device_id.get(
                device_id, (current_creation_time, current_creation_time)
            )
            start_end_time_by_device_id[device_id] = (
                min(start_time, current_creation_time),
                max(end_time, current_creation_time),
            )

        for device_id, current_amps in electricity_consumption_by_device_id.items():
            start_time, end_time = start_end_time_by_device_id[device_id]
            run_time_seconds = (end_time - start_time).total_seconds()
            electricity_consumption_by_device_id[device_id] = amps_to_kilowatt_hours(
                current_amps, seconds_to_hours(run_time_seconds)
            )

        if not electricity_consumption_by_device_id:
            client_requested_data = "No electricity data is available in the database"
        else:
            most_electricity_consumed = max(electricity_consumption_by_device_id.values())
            client_requested_data = "".join(
                f"{device_name_lookup[device_id]} consumed the most electricity among all devices at "
                f"{consumption:.2f} kilowatt hours\n"
                for device_id, consumption in electricity_consumption_by_device_id.items()
                if consumption == most_electricity_consumed
            )

    else:
        raise ValueError

    return client_requested_data

def main():
    print(f"\n{BLUE}* * * * * * * * IoT Smart Home Client * * * * * * * *{RESET}\n")
    
    # Obtains access to connection string safely
    load_dotenv()
    DATABASE_CONNECTION_STRING = psycopg2.connect(os.getenv("DATABASE_CONNECTION_STRING"))

    # Tests connection to Neon
    if DATABASE_CONNECTION_STRING:
        print(f"{GREEN}Connection with Neon successful!{RESET}")
    else:
        print(f"{RED}Nothing happened...{RESET}")

    cursor = DATABASE_CONNECTION_STRING.cursor()

    print("\nRunning server...")
    # Creates socket for network communication using IPV4 and TCP
    my_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host, port_num = str(sys.argv[1]), int(sys.argv[2])
    #  Tells the socket to associate itself with all possible host addresses and the provided port number
    my_tcp_socket.bind((host, port_num))
    # Listens to port for a response
    my_tcp_socket.listen(5)
    # Extracts info from the first client connection established
    client, client_address = my_tcp_socket.accept()
    print(f"{GREEN}Connection established!{RESET}")

    while True:

        # Recieves data (of max size of 1024 bytes) from client
        message_from_client = str((client.recv(1024)).decode())

        # Indicates Server-Client communication should cease
        if message_from_client == "":
            break
        else:
            print(f"{GREEN}Message from Client{RESET}: {message_from_client}")

        if message_from_client in VALID_QUERIES:
            query_index = VALID_QUERIES.index(message_from_client)
            try:
                server_message = get_client_requested_data(query_index, cursor)
            except psycopg2.Error as error:
                print(f"{RED}Database query failed: {error}{RESET}")
                DATABASE_CONNECTION_STRING.rollback()
                server_message = "Database query failed; see the server log for details."
        else:
            # Modifies the client message received to be all uppercased
            server_message = message_from_client.upper()

        # Replies to client by sending it an uppercased version of client's sent message
        client.send(bytearray(str(server_message), encoding='utf-8'))
        
    # Closes connection with Client
    client.close()
    print(f"{RED}Shutting down communications on server side...{RESET}")

    # Closes connection with Neon database
    DATABASE_CONNECTION_STRING.close()
    print(f"{RED}Shutting down connection with Neon...{RESET}")


if __name__ == "__main__":
    main()
