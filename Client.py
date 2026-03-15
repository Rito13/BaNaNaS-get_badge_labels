import socket
from threading import Thread, RLock
from os import _exit, path as os_path
from queue import Queue
from sys import argv
from time import sleep

lock = RLock()
GRF_IDS = {}
grf_file = ""


def int_from_bytes(bytes):
	out = 0
	i = 1
	for b in bytes:
		out += b * i
		i *= 256
	return out


def bytes_from_int(num, size=0):
	out = []
	while num:
		out.append(num % 256)
		num = num // 256
	while size and size > len(out):
		out.append(0)
	return out


def read_string(start, grf_info):
	out = []
	for b in grf_info[start:]:
		if b == 0:
			break
		out.append(chr(b))
	return "".join(out)


def decode_grf_info(grf_info):
	if grf_info[3] != 2:
		print("Got not grf.")
		return
	content_id = int_from_bytes(grf_info[4:8])
	filesize = int_from_bytes(grf_info[8:12])
	i = 12
	data = {}
	for key in ["name", "version", "url", "description"]:
		data[key] = read_string(i, grf_info)
		i += len(data[key]) + 1
	unique_id = hex(int_from_bytes(grf_info[i : i + 4]))
	md5 = int_from_bytes(grf_info[i + 4 : i + 20])
	print(content_id, filesize, data["name"], data["version"], unique_id, md5)
	lock.acquire()
	GRF_IDS[unique_id] = content_id
	lock.release()


def save_grf(grf_data, report_queue):
	global grf_file
	lock.acquire()
	if grf_file == "":
		lock.release()
		if grf_data[3] != 2:
			print("Got not grf.")
			return
		content_id = int_from_bytes(grf_data[4:8])
		filesize = int_from_bytes(grf_data[8:12])
		file_name = read_string(12, grf_data)
		print(content_id, filesize, file_name)
		lock.acquire()
		grf_file = os_path.join("grf_tars", f"{file_name}.tar")
		open(grf_file, "bw").close()  # Clear old content.
		lock.release()
		return
	if len(grf_data) == 3:
		grf_file = ""
		lock.release()
		print("Download completed!")
		report_queue.put(True)
		return
	with open(grf_file, "ba") as f:
		lock.release()
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
					length = b * 256 + packet[-1] - 1
					packet = [packet[-1]]
				f.write(str(b) + ",")
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

	for unique_id in argv[1:]:
		if unique_id[1] != "x":
			unique_id = f"0x{unique_id}"
		for i in range(ATTEMPTS):
			lock.acquire()
			if unique_id in GRF_IDS:
				contents.append(GRF_IDS[unique_id])
				lock.release()
				break
			lock.release()
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
		report_queue.get()
		contents = contents[1:]

	sleep(1)  # Give decoder some time, to clean.
	client_socket.close()  # close the connection
	_exit(0)


if __name__ == "__main__":
	client_program()
