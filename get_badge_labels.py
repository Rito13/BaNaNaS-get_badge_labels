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
	grf_id = 0
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
				elif data[i] == 0x08:  # Maybe it is an action 0x08 instead.
					grf_id = decode_dword(data[i + 5 : i + 1 : -1])  # Read grf id.
					if debug:
						print("GRF ID:", hex(grf_id))
			i = i + size
			size = decode_dword(data[i : i + 4])
	return out, private_out, hidden_out, grf_id


def find_grf_date(id, debug=False):
	"""Read last upload-date from BaNaNaS metadata."""
	dir = "bananas/newgrf/" + hex(id)[2:] + "/versions"
	if not os.path.isdir(dir):
		if debug:
			print("No data for:", hex(id))
		return Date.today()
	for file in os.listdir(dir):
		with open(dir + "/" + file, "r") as f:
			s = f.read()
			if s.find('availability: "savegames-only"') == -1 and s.find('availability: "new-games"') != -1:
				UD = "upload-date: "
				i = s.find(UD) + len(UD)
				date = Date.fromisoformat(s[i : i + 10])
				if debug:
					print("Date for", hex(id), "is", date.year, date.month, date.day)
				return date


def find_grf_name(id, debug=False):
	"""Read grf name from BaNaNaS metadata."""
	path = "bananas/newgrf/" + hex(id)[2:] + "/global.yaml"
	if not os.path.exists(path):
		if debug:
			print("No data for:", hex(id))
		return hex(id)[2:]
	with open(path, "r") as f:
		s = f.read()
		start = s.find('name: "') + 7
		end = s.find('"', start)
		return s[start:end]


def generate_markdown_page(labels, page_name, debug=False):
	labels = dict(labels)
	hierarchy = {}
	for label in sorted(labels.keys()):
		first_slash = label.find("/")
		if first_slash == -1:  # It is a class.
			hierarchy[label] = []
		else:  # It is a normall badge
			if label[:first_slash] not in labels:
				continue  # Skip badges that class for them was not introduced yet (they are invalid).
			hierarchy[label[:first_slash]].append(label)
	with open("gen_docs/" + page_name + ".md", "w") as md_file:
		md_file.write("# Classes\n")
		md_file.write("| Label | Introduced by | When | Comment |\n")
		md_file.write("| --- | --- | --- | --- |\n")
		for c in hierarchy.keys():
			label = "[{0}](#{0})".format(c)  # Link to a table for this class.
			grf_id = labels[c][0]
			if grf_id == -1:  # It comes from default badges by Peter Nelson.
				grf_id = "[OpenTTD default badges](https://github.com/OpenTTD/OpenTTD/pull/13655)"
			elif grf_id == -2:  # Introduced by community but not necessarily used in any grfs.
				grf_id = "[Community](https://www.tt-forums.net)"
			else:  # Introduced by grf from BaNaNaS.
				grf_id = "[{0}](https://bananas.openttd.org/package/newgrf/{1})".format(find_grf_name(grf_id, debug), hex(grf_id)[2:])
			when = "{0}-{1:02d}-{2:02d}".format(labels[c][1], labels[c][2], labels[c][3])  # Introduction date.
			md_file.write("| {0} | {1} | {2} | {3} |\n".format(label, grf_id, when, labels[c][4]))


if __name__ == "__main__":
	DEBUG = True

	for file in os.listdir("grfs"):
		if not file.endswith(".grf"):
			continue
		public, private, hidden, id = read_grf_file("grfs/" + file, DEBUG)

		date = None
		for label in public:
			if label not in PUBLIC_LABELS:
				date = date if date else find_grf_date(id, DEBUG)
				PUBLIC_LABELS[label] = [id, date.year, date.month, date.day, ""]
		uses = sorted(public + private + hidden)
		with open("uses/" + hex(id)[2:] + ".py", "w") as uses_x:
			uses_x.write("USES = " + uses.__str__())

	generate_markdown_page(PUBLIC_LABELS, "public_labels", DEBUG)

	with open("public_labels.py", "w") as public_labels:
		public_labels.write("PUBLIC_LABELS = " + PUBLIC_LABELS.__str__())
