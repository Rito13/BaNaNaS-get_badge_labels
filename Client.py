import socket
from threading import Thread, RLock
from os import _exit, path as os_path
from queue import Queue
from sys import argv
from time import sleep
from decode import int_from_bytes, bytes_from_int, read_string

lock = RLock()
GRF_IDS = {}
now_downloaded_file = ""


def decode_grf_info(grf_info):
	if grf_info[3] != 2:
		print("Got not grf.")
		return
	content_id = int_from_bytes(grf_info[4:8])
	filesize = int_from_bytes(grf_info[8:12])
	i = 12
	data = {}
	for key in ["name", "version", "url", "description"]:  # We don't access some of this but we need to read them in order to get unique_id.
		data[key] = read_string(i, grf_info)
		i += len(data[key]) + 1
	unique_id = hex(int_from_bytes(grf_info[i : i + 4]))
	md5 = int_from_bytes(grf_info[i + 4 : i + 20])
	print(content_id, filesize, data["name"], data["version"], unique_id, md5)

	lock.acquire()
	GRF_IDS[unique_id] = content_id
	lock.release()


def save_grf(grf_data, report_queue):
	global now_downloaded_file
	lock.acquire()  # WARNING: Has to be released before any return statement.
	if now_downloaded_file == "":
		lock.release()  # NOTE: We might return if we got not grf, so release lock first.
		if grf_data[3] != 2:
			print("Got not grf.")
			return
		content_id = int_from_bytes(grf_data[4:8])
		filesize = int_from_bytes(grf_data[8:12])  # Unused, because not sure what unit it is in.
		file_name = read_string(12, grf_data)
		print(content_id, filesize, file_name)

		lock.acquire()
		now_downloaded_file = os_path.join("grf_tars", f"{file_name}.tar")
		open(now_downloaded_file, "bw").close()  # Clear old content.
		lock.release()

		return
	if len(grf_data) == 3:
		now_downloaded_file = ""
		lock.release()  # NOTE: Lock acquired at the top.
		print("Download completed!")
		report_queue.put(True)  # Notify client_program() that we have successfully downloaded a grf.
		return
	with open(now_downloaded_file, "ba") as f:
		lock.release()  # NOTE: Lock acquired at the top.
		f.write(bytes(grf_data[3:]))


def decoder(soc, report_queue):
	open("out.txt", "w").close()  # Clear old content.
	length = 0
	packet = []
	while True:
		data = soc.recv(16000)
		with open("out.txt", "a") as f:
			for b in data:
				if length == -1:
					length += int_from_bytes([packet[-1], b])
					packet = [packet[-1]]
				f.write(str(b) + ",")  # Use comma (instead of space) because then vim does not wrap lines and file is easier to read. Also can copy paste to python list.
				packet.append(b)
				length -= 1
				if length == 0:
					if len(packet) > 2:
						match packet[2]:
							case 4:
								decode_grf_info(packet)
							case 6:
								save_grf(packet, report_queue)
							case _:
								print(f"Unknown packet type {packet[2]}")
					f.write("\n")


def client_program():
	host = "content.openttd.org"
	port = 3978  # socket server port number
	client_socket = socket.socket()  # instantiate
	client_socket.connect((host, port))

	report_queue = Queue()
	t1 = Thread(target=decoder, args=(client_socket, report_queue))
	t1.start()

	versions = ["vanilla", "100.0", "jgrpp", "100.0"]  # Big version numbers to prevent updating it with each new release.
	version_bytes = bytes([0]).join([s.encode() for s in versions + [""]])
	client_socket.send(bytes([*bytes_from_int(9 + len(version_bytes), 2), 0, 2, 255, 255, 255, 255, len(versions) // 2]) + version_bytes)
	sleep(1)  # Wait for info to be received.

	contents = []
	ATTEMPTS = 5  # Do only 5 attempts.

	for unique_id in argv[1:]:  # Get content id for each grf provided with command arguments. NOTE: content id can vary between connections.
		if unique_id[1] != "x":  # Only supports hexadecimal numbers.
			unique_id = f"0x{unique_id}"
		for i in range(ATTEMPTS):
			lock.acquire()
			if unique_id in GRF_IDS:
				contents.append(GRF_IDS[unique_id])
				lock.release()
				break
			lock.release()

			# The info about this grf did not came back from the server yet. Attempt to get it's content id later.
			if i == ATTEMPTS - 1:
				print(f"Could not find {unique_id} in databse.")
				break
			sleep(2**i)  # After each unsuccessful attempt sleep more.

	what = []
	for id in contents:
		what += bytes_from_int(id, 4)
	print(*what)
	client_socket.send(bytes([*bytes_from_int(5 + len(what), 2), 5, *bytes_from_int(len(what) // 4, 2), *what]))

	while len(contents) > 0:
		report_queue.get()  # Wait for files to download.
		contents = contents[1:]

	sleep(1)  # Give decoder some time, to clean.
	client_socket.close()  # close the connection
	_exit(0)


if __name__ == "__main__":
	client_program()
