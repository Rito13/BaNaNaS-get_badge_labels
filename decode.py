def int_from_bytes(bytes):
	"""Converts bytes in little endian to int."""
	out = 0
	i = 1
	for b in bytes:
		out += b * i
		i *= 256
	return out


def bytes_from_int(num, size=0):
	"""Converts int to bytes in little endian."""
	out = []
	while num:
		out.append(num % 256)
		num = num // 256
	while size and size > len(out):
		out.append(0)
	return out


def read_string(start, bytes):
	"""Reads string from bytes until 0x00 encountered. OTTD uses 0x00 to terminate strings."""
	out = []
	for b in bytes[start:]:
		if b == 0:
			break
		out.append(chr(b))
	return "".join(out)
