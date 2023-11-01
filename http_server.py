import logging
import socket
import argparse
import os
import time
from threading import Thread
import queue
import asyncio
import sys
from signal import signal, SIGPIPE, SIG_DFL

# takes care of BrokenPipeError
signal(SIGPIPE, SIG_DFL)

WAIT_TIME = 5
DEFAULT_RECEIVE_SIZE = 1024
DEFAULT_NUMBER_OF_THREADS = 10
END_OF_HEADER_OR_REQUEST = "\r\n\r\n"
END_OF_REQUEST_LENGTH = 4
COMMON_HEADER = "Content-Length: "
METHOD_NOT_ALLOWED = "HTTP/1.1 405 Method Not Allowed\r\n" + COMMON_HEADER
SUCCESS = "HTTP/1.1 200 OK\r\n" + COMMON_HEADER
NOT_FOUND = "HTTP/1.1 404 Page Not Found\r\n" + COMMON_HEADER
NOT_FOUND_PAGE = "www/404.html"
DEFAULT_PAGE = "/page.html"


# function to send the response back to the client
def send_response(conn, file_path, header):
    send_number = 0
    # only deal with file if file_path is given
    if file_path:
        # header part
        file_size = os.path.getsize(file_path)
        logging.info(f"File size is: {file_size}")
        response_header = header + str(file_size) + END_OF_HEADER_OR_REQUEST
        conn.send(response_header.encode())

        # actual file to return to client
        f = open(file_path, "rb")
        # loop until EOF is reached
        while True:
            file_content = f.read(DEFAULT_RECEIVE_SIZE)
            if not file_content:
                break
            conn.sendall(file_content)
            send_number += 1
            logging.info(send_number)
    else:
        conn.send((header + "0" + END_OF_HEADER_OR_REQUEST).encode())


# async version of the send_response function
async def async_send_response(file_path, header, writer):
    send_number = 0
    # only deal with file if file_path is given
    if file_path:
        # header part
        file_size = os.path.getsize(file_path)
        logging.info(f"File size is: {file_size}")
        response_header = header + str(file_size) + END_OF_HEADER_OR_REQUEST
        writer.write(response_header.encode())
        await writer.drain()

        # actual file to return to client
        f = open(file_path, "rb")
        # loop until EOF is reached
        while True:
            file_content = f.read(DEFAULT_RECEIVE_SIZE)
            if not file_content:
                break
            writer.write(file_content)
            await writer.drain()
    else:
        writer.write(header + "0" + END_OF_HEADER_OR_REQUEST).encode()
        await writer.drain()


# function to get header given a code
def get_header(code):
    if code == 200:
        return SUCCESS
    if code == 404:
        return NOT_FOUND
    if code == 405:
        return METHOD_NOT_ALLOWED


# function to check if the requested file exists
def is_request_file_exist(request_file):
    if request_file == "/":
        request_file = DEFAULT_PAGE
    logging.info(f"Checking if {root_folder + request_file} exists...")
    return os.path.isfile(root_folder + request_file)


# function to process_request
def process_request(conn, request):
    first_line = request[0 : request.index("\r\n")]
    info = first_line.split(" ")
    method = info[0]
    request_file = info[1]
    logging.info(f"Requested file is: {request_file}")

    # return 405 Method Not Allowed
    if method != "GET":
        send_response(conn, 0, get_header(405))
        return

    # check if requested file exists
    if not is_request_file_exist(request_file):
        send_response(conn, NOT_FOUND_PAGE, get_header(404))
        return

    # check if the reqeusted file is the default file
    if request_file == "/":
        send_response(conn, root_folder + DEFAULT_PAGE, get_header(200))
        return

    # otherwise return the requested file
    send_response(conn, root_folder + request_file, get_header(200))


# async version of process_request
async def async_process_request(request, writer):
    first_line = request[0 : request.index("\r\n")]
    info = first_line.split(" ")
    method = info[0]
    request_file = info[1]
    logging.info(f"Requested file is: {request_file}")

    # return 405 Method Not Allowed
    if method != "GET":
        await async_send_response(0, get_header(405), writer)
        return

    # check if requested file exists
    if not is_request_file_exist(request_file):
        await async_send_response(NOT_FOUND_PAGE, get_header(404), writer)
        return

    # check if the reqeusted file is the default file
    if request_file == "/":
        await async_send_response(root_folder + DEFAULT_PAGE, get_header(200), writer)
        return

    # otherwise return the requested file
    await async_send_response(root_folder + request_file, get_header(200), writer)


# function to run with a given port
def run(port):
    global q
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("", port))
    server_socket.listen()
    logging.info(f"Listening on port {port}")
    threads = []

    # create bunch of threads
    if args.concurrency == "thread-pool":
        q = queue.Queue()
        logging.info(f"Creating {DEFAULT_NUMBER_OF_THREADS} thread...")
        for i in range(DEFAULT_NUMBER_OF_THREADS):
            t = Thread(target=worker, daemon=True, args=[i + 1])
            t.start()
            threads.append(t)

    # watch for KeyboardInterrupt
    try:
        # loop forever until KeyboardInterrupt is detected (Exception thrown)
        while True:
            conn, address = server_socket.accept()
            logging.info(f"Connection from: {address}")

            # put connections to queue or run create new threads on demand
            if args.concurrency == "thread-pool":
                logging.info(f"Putting connection {address} into the queue...")
                q.put(conn)
            elif args.concurrency == "thread":
                t = Thread(target=handle_client, args=[conn])
                t.start()
                threads.append(t)
    except KeyboardInterrupt:
        logging.info("Keyboard Interrupt Detected!")
        # put None in the connection quese
        if args.concurrency == "thread-pool":
            for _ in range(DEFAULT_NUMBER_OF_THREADS):
                q.put(None)

        # loop through all threads and join them
        for t in threads:
            t.join()
        return


# function to handle connections, used for thread-pool
def worker(thread_number):
    logging.info(f"This is tread number {thread_number}")
    while True:
        conn = q.get()
        if conn is None:
            break
        logging.info(f"Thread number {thread_number} processing client...")
        handle_client(conn)
        logging.info(f"Thread number {thread_number} is done!")


# function to handle client
def handle_client(conn):
    data_string = ""
    # loop until current client disconnects
    while True:
        # this try-except block is for catching ConnectionResetError
        try:
            data = conn.recv(DEFAULT_RECEIVE_SIZE).decode()
        except ConnectionResetError:
            logging.info("Client disconnected...")
            data_string = ""
            break

        # if data is 0, meaning client disconnected, up one level and wait
        if not data:
            logging.info("Client disconnected...")
            data_string = ""
            break

        data_string += data
        logging.info(f"Received: {data}")
        logging.info(f"Current Data String:\n{data_string}")

        # check if "/r/n/r/n" is in the request
        if END_OF_HEADER_OR_REQUEST in data:
            end_of_request_index = data_string.index(END_OF_HEADER_OR_REQUEST)
            request = data_string[0:end_of_request_index]
            logging.info(f"Complete request received:\n{request}")
            data_string = data_string[end_of_request_index + END_OF_REQUEST_LENGTH :]
            # wait 5 seconds before processing the request
            if args.delay:
                time.sleep(WAIT_TIME)
            process_request(conn, request)


# async version of the handle_client function
async def async_handle_client(reader, writer):
    # catches the KeyboardInterrupt Error
    try:
        data_string = ""
        # loop until current client disconnects
        while True:
            # this try-except block is for catching ConnectionResetError
            try:
                data = (await reader.read(DEFAULT_RECEIVE_SIZE)).decode()
            except ConnectionResetError:
                logging.info("Client disconnected...")
                data_string = ""
                break

            # if data is 0, meaning client disconnected, up one level and wait
            if not data:
                logging.info("Client disconnected...")
                data_string = ""
                break

            data_string += data
            logging.info(f"Received: {data}")
            logging.info(f"Current Data String:\n{data_string}")

            # check if "/r/n/r/n" is in the request
            if END_OF_HEADER_OR_REQUEST in data:
                end_of_request_index = data_string.index(END_OF_HEADER_OR_REQUEST)
                request = data_string[0:end_of_request_index]
                logging.info(f"Complete request received:\n{request}")
                data_string = data_string[
                    end_of_request_index + END_OF_REQUEST_LENGTH :
                ]
                # wait 5 seconds before processing the request
                if args.delay:
                    time.sleep(WAIT_TIME)
                await async_process_request(request, writer)
    except KeyboardInterrupt:
        logging.info("Keyboard Interrupt Detected!")
        sys.exit(0)


# async version of the run function
async def async_run(port):
    server = await asyncio.start_server(async_handle_client, "localhost", port)
    logging.info(f"Listening on port {port}")
    async with server:
        await server.serve_forever()


# function to parse arguments
def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=False,
        default=8085,
        help="port to bind to",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        required=False,
        action="store_true",
        help="turn on debugging output",
    )
    parser.add_argument(
        "-d",
        "--delay",
        required=False,
        action="store_true",
        help="add a delay for debugging purposes",
    )
    parser.add_argument(
        "-f",
        "--folder",
        type=str,
        required=False,
        default=".",
        help="folder from where to serve from",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=str,
        required=False,
        default="thread",
        choices=["thread", "thread-pool", "async"],
        help="concurrency methodology to use",
    )
    return parser.parse_args()


# main function
if __name__ == "__main__":
    global root_folder
    args = parse_arguments()
    root_folder = args.folder
    # if verbose flag is high, turn on verbose
    if args.verbose:
        logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
    # execute the appropriate run function
    if args.concurrency == "async":
        asyncio.run(async_run(args.port))
    else:
        run(args.port)
