import socket
import ipaddress

VALID_QUERIES = ["What is the average moisture inside my kitchen fridge in the past three hours?",
                 "What is the average water consumption per cycle in my smart dishwasher?",
                 "Which device consumed more electricity among my three IoT devices?"]

# ANSI color codes for terminal output
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def output_query_options():
    for i in range(len(VALID_QUERIES)):
        print(f"{i+1}. {YELLOW}{VALID_QUERIES[i]}{RESET}")
    print()

def main():
    print(f"\n{BLUE}* * * * * * * * IoT Smart Home Client * * * * * * * *{RESET}")

    # Loop to ensure that the user inputs a valid IP address for the Server
    while True:
        try:
            server_ip_address = str(ipaddress.IPv4Address(
                input(f"{CYAN}\nInput the IP Address of the Server: {RESET}"))
                )
        except ipaddress.AddressValueError:
            print(f"{RED}Invalid IP Address inputted.{RESET}")
            print("* * * * * * * * * * * * * * * * * * * * * * * * * *")
            continue
        print("* * * * * * * * * * * * * * * * * * * * * * * * * *")
        break

    # Ensures that the user acting as Client inputs a valid port number to communicate with Server
    while True:
        try:
            # User inputs port number
            server_port_num = int(
                input(f"{CYAN}\nInput the Port Number of the Server: {RESET}"))
            # Ensures that the port number inputted is not invalid
            if server_port_num not in range(1, 65536):
                raise ValueError

            # Creates socket for network communication using IPV4 and TCP
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((server_ip_address, server_port_num))
        # Catches any errors associated with the port number
        except ValueError:
            print(f"{RED}Invalid Port Number inputted. Should be between 1-65,535.{RESET}")
            print("* * * * * * * * * * * * * * * * * * * * * * * * * *")
            continue
        except Exception as e:
            print(f"{RED}Unexpected Error: {e}{RESET}")
            print("* * * * * * * * * * * * * * * * * * * * * * * * * *")
            continue
        print("* * * * * * * * * * * * * * * * * * * * * * * * * *")
        break

    # Loop for client to repeatedly send and receive messages between itself and the Server
    while True:
        output_query_options()
        # User inputs a message to send to the server
        message = input("Input a Message to Send to the Server: ")

        if message in ["1", "2", "3"]:
            query_index = int(message) - 1
            message = VALID_QUERIES[query_index]
        if message not in VALID_QUERIES and message != "":
            print(f"{RED}\nSorry, this query cannot be processed. Please try one of the following:{RESET}\n")
            continue

        print("* * * * * * * * * * * * * * * * * * * * * * * * * *")

        # Sends message to Server over communication link
        client.send(bytearray(str(message), encoding="utf-8"))

        # Indicates whether Server-Client communication should cease
        if message == "":
            break

        # Receives message (of max size of 1024 bytes) from server
        server_response = client.recv(1024).decode()

        # Displays server replay
        print(f'{GREEN}Client Received: {RESET}{server_response}')
        print("* * * * * * * * * * * * * * * * * * * * * * * * * *")

    # Closes connection with Server
    client.close()
    print(f"{RED}Shutting down communications on client side...{RESET}")


if __name__ == "__main__":
    main()
