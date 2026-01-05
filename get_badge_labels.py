import os
from public_labels import PUBLIC_LABELS
from datetime import date as Date


def decode_dword(dword):
	"""Uses little-endian byte order."""
	return dword[0] + (dword[1] << 8) + (dword[2] << 16) + (dword[3] << 24)


def read_grf_file(file, debug=False):
	"""Parses prowided .grf file and returns 3 arrays of labels: public, private and hidden."""
	# Outputs
	out = []
	private_out = []
	hidden_out = []
	with open(file, "rb") as f:
		data = f.read()
		sprites_start = decode_dword(data[10:14])
		i = 15  # i short for iterator. 15 skips file header of grf format 2.
		size = decode_dword(data[i : i + 4])  # Read size of first sprite.
		while size != 0:  # Size == 0 marks end of data section.
			i = i + 5  # Skip size dword and info byte.
			if data[i - 1] != 0xFF:  # Check if info byte is not a pseudo sprite.
				if data[i - 1] != 0xFD:  # Check if info byte is not a reference to sprite section.
					print("invalid info byte:", hex(data[i - 1]))
					break  # Corruption or format 1 encountered.
			else:  # Info byte is a pseudo sprite.
				if data[i] == 0x00 and data[i + 1] == 0x15:  # Check if it is action 0x00 feature 0x15.
					if debug:  # If debug print all bits for that sprite.
						print(size, " * ", end=" ")
						for c in data[i : i + size]:
							print(hex(c), end=" ")
						print()
					props = data[i + 2]  # How many properties are changed by this action 0x00.
					badges = data[i + 3]  # How many badges are changed by this action 0x00.
					j = i + 6 + badges  # Skip to the property number.
					for __p__ in range(props):
						prop = data[j]  # Read what property is set.
						for __b__ in range(badges):
							if prop == 0x09:  # Prop is badge flags.
								j += 4
							elif prop == 0x08:  # Prop is badge label.
								j += 1
								label = ""
								while data[j] != 0x00:  # Byte 0x00 terminates the string.
									label += chr(data[j])
									j += 1
								first_slash = label.find("/")
								if debug:
									if first_slash == -1:  # A class badge.
										print("class_label:", label)
									else:
										print("label:", label)
								# Add badge label to corresponding output.
								if label[0] == "_" or label[first_slash + 1] == "_":  # Badge is private or hidden.
									if label[0:2] == "__" or label[first_slash + 1 : first_slash + 3] == "__":
										hidden_out.append(label)
									else:  # Badge is private.
										private_out.append(label)
								else:  # Badge is public.
									out.append(label)
							else:
								print("invalid prop:", prop)  # Corruption or newer grf version.
								j += 1  # Skip one byte per badge.
						j += 1
			i = i + size
			size = decode_dword(data[i : i + 4])
	return out, private_out, hidden_out


if __name__ == "__main__":
	DEBUG = False

	for file in os.listdir("grfs"):
		if not file.endswith(".grf"):
			continue
		public, private, hidden = read_grf_file("grfs/" + file, DEBUG)
		for label in public:
			if label not in PUBLIC_LABELS:
				date = Date.today()
				PUBLIC_LABELS[label] = [file, date.year, date.month, date.day, ""]

	with open("public_labels.py", "w") as public_labels:
		public_labels.write("PUBLIC_LABELS = " + PUBLIC_LABELS.__str__())
