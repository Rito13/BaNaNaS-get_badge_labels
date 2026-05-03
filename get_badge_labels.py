import os
from datetime import date as Date
import yaml
from decode import int_from_bytes, is_extended_byte_a_word, int_from_extended_byte, read_string
from functools import cmp_to_key


class LabelFlags:
	AgingBadly = 0
	Private = 1


FORMAT_2_HEADER = [0x00, 0x00, 0x47, 0x52, 0x46, 0x82, 0x0D, 0x0A, 0x1A, 0x0A]
FRAX = ["Passengers", "Mail", "Express", "Armoured", "OpenBulk", "PieceGoods", "LiquidBulk", "Refrigerated", "GasBulk", "CoveredBulk", "Flatbed", "PowderBulk", "Weird", "Potable", "Non-Potable", "Special"]

RAIL_TYPE_PROPS = {
	0x0A: 2,  # Rail construction dropdown text
	0x0B: 2,  # Build vehicle window caption
	0x0C: 2,  # Autoreplace text
	0x0D: 2,  # New engine text
	0x0E: [1, 4],  # Compatible rail type list
	0x0F: [1, 4],  # Powered rail type list
	0x10: 1,  # Rail type flags
	0x11: 1,  # Curve speed advantage multiplier
	0x12: 1,  # Station (and depot) graphics
	0x13: 2,  # Construction costs
	0x14: 2,  # Speed limit
	0x15: 1,  # Acceleration model
	0x16: 1,  # Minimap colour
	0x17: 4,  # Introduction date
	0x18: [1, 4],  # Introduction required rail type list
	0x19: [1, 4],  # Introduced rail type list
	0x1A: 1,  # Sort order
	0x1B: 2,  # Rail type name
	0x1C: 2,  # Infrastructure maintenance cost factor
	0x1D: [1, 4],  # Alternate rail type labels that shall be "redirected" to this rail type
	0x1E: [2, 2],  # Badges
}

PROPS = {
	0x15: {  # Badges
		0x09: 4  # Badge flags
	},
	0x0B: {  # Cargos
		0x08: 1,  # Cargo bit
		0x0A: 2,  # Singular name
		0x0B: 2,  # One of
		0x0C: 2,  # Multiple of
		0x0D: 2,  # Abbreviation
		0x0E: 2,  # Icon
		0x0F: 1,  # Weight
		0x10: 1,  # Penalty times
		0x11: 1,  # --""--
		0x12: 4,  # Base price
		0x13: 1,  # Station colour
		0x14: 1,  # Payment colour
		0x15: 1,  # Freight status
		0x18: 1,  # Substitute type
		0x19: 2,  # Multiplier
		0x1A: 1,  # Flags
		0x1B: 2,  # Unit short
		0x1C: 2,  # Unit long
		0x1D: 2,  # Capacity
		0x1E: 1,  # Production effect
		0x1F: 2,  # Production multiplier
	},
	0x10: RAIL_TYPE_PROPS,  # Rail types
	0x12: RAIL_TYPE_PROPS,  # Road types (All road type parametes consist in rail type ones.)
	0x13: RAIL_TYPE_PROPS,  # Tram types (Have same params as road types.)
}


def colour_text(text, colour):
	return r"$\textcolor{" + colour + r"}{\textsf{" + text + "}}$"


RED_ZERO = colour_text("0", "red")
OPENTTD_IMAGE = "![OpenTTD](https://github.com/OpenTTD/OpenTTD/blob/master/media/openttd.16.png?raw=true)"
INVALID_SUB_STRINGS = [chr(n) for n in range(0x88, 0x98 + 1)] + ["\xc3\x9e"] + [chr(0x9A) + chr(n) for n in range(0x00, 0x21 + 1)]


def match_string(item, label, strings, out, debug=False):
	if item not in strings:
		return False
	string = strings[item]
	for s in INVALID_SUB_STRINGS:
		string = string.replace(s, "")
	out[label] = string
	if debug:
		print(label, "\t\t", string)
	return True


def find_key_for_value(dictionary, value):
	for key in dictionary.keys():
		if dictionary[key] == value:
			return key
	return None


def read_grf_file(file, debug=False):
	"""Parses prowided .grf file and returns 3 arrays of labels: public, private and hidden."""
	# Outputs
	out = []
	private_out = []
	hidden_out = []
	strings = {key: {} for key in PROPS}
	badge_strings = {}
	cargo_strings = {}
	grf_id = 0
	cargos_out = {}
	rrtt_out = {0x10: [], 0x12: [], 0x13: []}  # rrtt - Rail, road, tram types
	rrtt_strings = {key: {} for key in rrtt_out}
	with open(file, "rb") as f:
		data = f.read()
		badges = {}
		cargos = {}
		rrtt = {key: {} for key in rrtt_out}
		format = 2 if FORMAT_2_HEADER == list(data[0 : len(FORMAT_2_HEADER)]) else 1
		if debug:
			print("Format", format)
		if format == 2:
			_sprites_start = int_from_bytes(data[10:14])  # Remove leading `_` if used.
			compression = data[14]  # Compression format of the data section.
			i = 15  # i short for iterator. 15 skips file header of grf format 2.
			size = int_from_bytes(data[i : i + 4])  # Read size of first sprite. Format 2 used dword sizes.
		else:
			i = 0  # Format 1 does not have file header.
			compression = 0  # Format 1 is not compressed.
			size = int_from_bytes(data[i : i + 2])  # Format 1 uses word sizes.
		if compression != 0:
			print("invalid compression format:", compression)
			size = 0  # Corruption, so skip the while loop.
		while size != 0:  # Size == 0 marks end of data section.
			i = i + (5 if format == 2 else 3)  # Skip size and info byte.
			if data[i - 1] != 0xFF:  # Check if info byte is not a pseudo sprite.
				if format == 2 and data[i - 1] != 0xFD:  # Check if info byte is not a reference to sprite section.
					print("invalid info byte:", hex(data[i - 1]))
					break  # Corruption.
				elif format == 1:
					if data[i - 1] == 0xFD:
						print("invalid info byte:", hex(data[i - 1]))
						break  # Corruption.
					if not data[i - 1] & 2:  # Image is compressed, but the size is of uncompressed version.
						if debug:
							print("info byte:", hex(data[i - 1]), "(bit 2 is not set)")
						size -= 8  # Substract the image header.
						i += 7  # Skip the image header.
						while size > 0:
							j = data[i]
							i += 1  # Skip the j byte.
							if j & 0x80:  # j is backward pointer.
								j = -(int.from_bytes(bytes([j]), signed=True) >> 3)  # Strip the size part from the j.
								i += 1  # Next byte is also part of the pointer. Skip it.
							else:  # j is the chunk size.
								j = 0x80 if j == 0 else j  # Chunk size can't be 0.
								if j > size:
									print("invalid size in compressed image")
									break  # The chunk can't fit into the sprite.
								i += j  # Skip the chunk.
							size -= j  # Substract "decompressed" pixels from image size.
						if size:
							break  # Corruption.
					else:
						size -= 1  # In format 1 size counts the info byte.
			else:  # Info byte is a pseudo sprite.
				feature = data[i + 1]
				if data[i] == 0x00 and feature in PROPS:  # Check if it is action 0x00 and if we handle that feature.
					if debug:  # If debug print all bits for that sprite.
						print(size, " * ", end=" ")
						for c in data[i : i + size]:
							print(hex(c), end=" ")
						print()
					props = data[i + 2]  # How many properties are changed by this action 0x00.
					num_of = data[i + 3]  # How many items are changed by this action 0x00.
					first = int_from_extended_byte(data[i + 4 : i + 7])
					j = i + 4 + (3 if is_extended_byte_a_word(data[i + 4]) else 1)  # Skip to the property number.
					for __p__ in range(props):
						prop = data[j]  # Read what property is set.
						if prop in PROPS[feature]:
							for _ in range(num_of):
								if isinstance(PROPS[feature][prop], (list, tuple)):
									j += 1
									n = int_from_bytes(data[j : j + PROPS[feature][prop][0]])
									j += n * PROPS[feature][prop][1]
								else:
									j += PROPS[feature][prop]
						elif feature == 0x15 and prop == 0x08:  # Prop is badge label.
							for b in range(num_of):
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
								match_string(first + b, label, strings[feature], badge_strings, debug)
								badges[first + b] = label
						elif feature == 0x0B and prop == 0x17:  # Prop is cargo label.
							for c in range(num_of):
								label = chr(data[j + 1]) + chr(data[j + 2]) + chr(data[j + 3]) + chr(data[j + 4])  # Cargo label is always 4 chars.
								j += 4
								if debug:
									print("cargo_label:", label)
								if label != "\00\00\00\00":
									cargos_out[label] = cargos_out.pop(first + c) if first + c in cargos_out else -(first + c) - 1  # Store cargo index as negative number to distinguish it from cargo classes.
									if first + c in cargos:
										match_string(cargos.pop(first + c), label, strings[feature], cargo_strings, debug)
										# cargos[cargos.pop(first + c)] = label
									else:
										cargos[first + c] = label
						elif feature == 0x0B and prop == 0x09:  # Prop is cargo name.
							for c in range(num_of):
								id = int_from_bytes(data[j + 1 : j + 3])
								if first + c in cargos:
									match_string(id, cargos.pop(first + c), strings[feature], cargo_strings, debug)
									# cargos[id] = cargos.pop(first + c)
								else:
									cargos[first + c] = id
								j += 2
						elif feature == 0x0B and prop == 0x16:  # Prop is cargo classes.
							for c in range(num_of):
								classes = int_from_bytes(data[j + 1 : j + 3])
								label = find_key_for_value(cargos_out, -(first + c) - 1)  # Find related label without cargo classes set.
								if label:
									cargos_out[label] = classes
								else:  # Prop 0x17 hasn't been provided yet.
									cargos_out[first + c] = classes
								j += 2
						elif prop == 0x08 and feature in rrtt_out:  # Prop is rail, road or tram label.
							for t in range(num_of):
								label = chr(data[j + 1]) + chr(data[j + 2]) + chr(data[j + 3]) + chr(data[j + 4])  # RRTt label is always 4 chars.
								j += 4
								if debug:
									print("rrtt_label:", label)
								rrtt_out[feature].append(label)
								if first + t in rrtt[feature]:
									match_string(rrtt[feature].pop(first + t), label, strings[feature], rrtt_strings[feature], debug)
								else:
									rrtt[feature][first + t] = label
						elif prop == 0x09 and feature in rrtt_out:  # Prop is rail, road or tram name.
							for t in range(num_of):
								id = int_from_bytes(data[j + 1 : j + 3])
								if first + t in rrtt[feature]:
									match_string(id, rrtt[feature].pop(first + t), strings[feature], rrtt_strings[feature], debug)
								else:
									rrtt[feature][first + t] = id
								j += 2
						else:
							print("invalid prop:", prop)  # Corruption or newer grf version.
							break  # We don't know how long this property is, therefore we can't read any more properties :(
						j += 1
				elif data[i] == 0x08:  # Maybe it is an action 0x08 instead.
					grf_id = int_from_bytes(data[i + 5 : i + 1 : -1])  # Read grf id.
					if debug:
						print("GRF ID:", hex(grf_id))
				elif data[i] == 0x04 and feature in PROPS:  # Might also be text string.
					number_of_strings = data[i + 3]
					if data[i + 2] & 0x7F == 0x7F:  # Read only default language.
						if debug:  # If debug print all bits for that sprite.
							print(size, " * ", end=" ")
							for c in data[i : i + size]:
								print(hex(c), end=" ")
							print()
						offset = int_from_extended_byte(data[i + 4 : i + 7])
						j = i + 4 + (3 if is_extended_byte_a_word(data[i + 4]) else 1)  # Skip to the text.
						if data[i + 2] & 0x80:  # Offset is a word, not an extended byte.
							offset = int_from_bytes(data[i + 4 : i + 6])
							j = i + 6
						for item in range(offset, offset + number_of_strings):
							string = read_string(j, data)
							strings[feature][item] = string
							if feature == 0x15 and item in badges:
								match_string(item, badges.pop(item), strings[feature], badge_strings, debug)
							elif feature == 0x0B and item in cargos:
								pass  # match_string(item, cargos.pop(item), strings[feature], cargo_strings, debug)
							j += len(string) + 1  # Text is followed by 0x00 byte.
			i = i + size
			if i >= len(data):
				print("reached outside the file")
				break  # Corruption.
			size = int_from_bytes(data[i : i + (4 if format == 2 else 2)])
	for key, value in list(cargos_out.items()):  # Clone dict as we want to delete elements from it inside the loop.
		if isinstance(key, int):
			cargos_out.pop(key)  # Key is a cargo id and not label.
		elif value < 0:
			cargos_out[key] = None
		else:
			cargos_out[key] = f"0b{value:016b}"
	return out, private_out, hidden_out, grf_id, badge_strings, cargos_out, cargo_strings, rrtt_out, rrtt_strings


def find_grf_date(id, debug=False):
	"""Read last upload-date from BaNaNaS metadata."""
	dir = os.path.join("bananas", "newgrf", hex(id)[2:], "versions")
	if not os.path.isdir(dir):
		if debug:
			print("No data for:", hex(id))
		return Date.today()
	for file in os.listdir(dir):
		with open(os.path.join(dir, file), "r") as f:
			version_data = yaml.safe_load(f)
			if version_data["availability"] == "new-games":
				date = version_data["upload-date"]
				if debug:
					print("Date for", hex(id), "is", date.year, date.month, date.day)
				return date
	if debug:
		print(hex(id), "is no longer available for new games.")
	return Date.today()  # But somehow we have downloaded it.


def find_grf_name(id, debug=False):
	"""Read grf name from BaNaNaS metadata."""
	path = os.path.join("bananas", "newgrf", hex(id)[2:], "global.yaml")
	if not os.path.exists(path):
		if debug:
			print("No data for:", hex(id))
		return hex(id)[2:]
	with open(path, "r") as f:
		global_data = yaml.safe_load(f)
		return global_data["name"]


def create_hierarchy(labels, required_flags: dict, debug=False, has_classes=True):
	flags_mask = 0
	flags_values = 0
	for flag in required_flags:
		flags_mask |= 1 << flag
		flags_values |= required_flags[flag] << flag
	labels = dict(labels)
	hierarchy = {-1: None} if has_classes else {"Labels": []}
	for label in sorted(labels.keys()):
		if labels[label][5] & flags_mask != flags_values:
			continue
		first_slash = label.find("/")
		if not has_classes:
			hierarchy["Labels"].append(label)
		elif first_slash == -1:  # It is a class.
			hierarchy[label] = []
		else:  # It is a normall badge
			class_label = label[:first_slash]
			if class_label not in hierarchy:
				if class_label not in labels:
					if debug:
						print("No class for badge:", label)
					labels[class_label] = [labels[label][0], labels[label][1], labels[label][2], labels[label][3], "AUTO GENERATED CLASS", RED_ZERO]
				hierarchy[class_label] = []
			hierarchy[class_label].append(label)
	if has_classes:
		hierarchy[-1] = list(hierarchy.keys())
		hierarchy[-1].remove(-1)
	for c in hierarchy.keys():
		hc = hierarchy[c]
		hierarchy[c] = {}
		for b in hc:
			hierarchy[c][b] = labels[b]
	return hierarchy


def generate_markdown_page(hierarchy, page_name, debug=False, countable_data=None):
	with open(os.path.join("gen_docs", f"{page_name}.md"), "w") as md_file:
		for c in hierarchy.keys():
			if c == -1:  # It is a classes table.
				md_file.write("# Classes\n")
			else:  # It is a table for specific class.
				md_file.write("\n# {}\n".format(c))
			cd_title = "| " + " | ".join(countable_data) if countable_data else ""
			md_file.write(f"| Label | Introduced by | When | Comment {cd_title}| O. |\n")
			cd_line = "| " + " | ".join(["---" for _ in countable_data]) if countable_data else ""
			md_file.write(f"| --- | --- | --- | --- {cd_line}| --- |\n")
			for b in hierarchy[c]:
				label = b
				data = hierarchy[c][b]
				if c == -1:  # It is a classes table.
					label = "[{0}](#{0})".format(b)  # Link to a table for this class.
				grf_id = data[0]
				if grf_id == -1:  # It comes from default badges by Peter Nelson.
					grf_id = "[OpenTTD default badges](https://github.com/OpenTTD/OpenTTD/pull/13655)"
				elif grf_id == -2:  # Introduced by community but not necessarily used in any grfs.
					grf_id = "[Community](https://www.tt-forums.net)"
				elif grf_id == -3:  # Introduced by Chris Sawyer in TTD.
					grf_id = "[TTD](https://www.tt-wiki.net/wiki/Main_Page)"
				elif grf_id < -3:  # Introduced by community in OTTD. GRF id is - commit hash in decimal system.
					grf_id = f"[OTTD](https://github.com/OpenTTD/OpenTTD/commit/{-grf_id:x})"
				else:  # Introduced by grf from BaNaNaS.
					grf_id = "[{0}](https://bananas.openttd.org/package/newgrf/{1})".format(find_grf_name(grf_id, debug), hex(grf_id)[2:])
				when = "{0}-{1:02d}-{2:02d}".format(data[1], data[2], data[3])  # Introduction date.
				comment = data[4] if data[4] else data[6]  # Use string from grf if no comment provided.
				md_file.write("| {0} | {1} | {2} | {3} {5}| {4} |\n".format(label, grf_id, when, comment, data[-1], f"| {data[-2]} " if countable_data else ""))


def link_with_grf_ids(li):
	return '[{0}](https://bananas.openttd.org/?message=GRFs:+{2} "{1}")'.format(len(li), ", ".join(li), ",+".join(li))


def FRAX_from_binary(binary):
	ids = int(binary, 2)
	out = []
	for i in range(len(FRAX)):
		if ids & (1 << i):
			out.append(FRAX[i])
	return "Empty" if len(out) == 0 else ("[" + ", ".join(out) + "]")


def add_uses_to_labels(labels, key, debug=False):
	start_size = len(labels[next(iter(labels))])
	if not os.path.isdir("uses"):
		return
	has_countable_data = False
	for file in sorted(os.listdir("uses")):
		if file[-5:] != ".yaml":
			continue  # Someone has put invalid file into this directory.
		grf_id = file[:-5]
		with open(os.path.join("uses", file), "r") as f:
			module = yaml.safe_load(f)
			module = module if not isinstance(module, dict) else module[key] if key in module else []
			if isinstance(module, dict):
				has_countable_data = True
		for label in module:
			if label not in labels:
				continue  # Lable from another scope.
			if len(labels[label]) == start_size:
				if isinstance(module, dict):
					labels[label].append({module[label]: [grf_id]} if module[label] else {})
				labels[label].append([grf_id])
			else:
				labels[label][-1].append(grf_id)
				if isinstance(module, dict) and module[label]:
					labels[label][-2][module[label]] = labels[label][-2].get(module[label], []) + [grf_id]
	for label in labels.keys():
		if len(labels[label]) == start_size:
			if has_countable_data:
				labels[label].append("")
			labels[label].append(RED_ZERO)
			if labels[label][0] >= 0:
				if debug:
					pass  # print(label, "is aging badly.")
				labels[label][5] |= 1 << LabelFlags.AgingBadly
		else:
			labels[label][-1] = link_with_grf_ids(labels[label][-1])
			if has_countable_data:
				ordered = list(labels[label][-2].items())

				def compare(a, b):
					return len(b[1]) - len(a[1])

				ordered = sorted(ordered, key=cmp_to_key(compare))
				labels[label][-2] = "<br>".join([link_with_grf_ids(e[1]) + (OPENTTD_IMAGE if "OpenTTD" in e[1] else "") + ": " + FRAX_from_binary(e[0]) for e in ordered])


if __name__ == "__main__":
	DEBUG = True
	BADGES_KEY = "badges"
	CARGOS_KEY = "cargos"
	RAIL_KEY = "rail_types"
	ROAD_KEY = "road_types"
	TRAM_KEY = "tram_types"

	def rrtt_feature_to_key(feature):
		match feature:
			case 0x10:
				return RAIL_KEY
			case 0x12:
				return ROAD_KEY
			case 0x13:
				return TRAM_KEY
			case _:
				return None

	with open("labels.yaml", "r") as f:
		labels = yaml.safe_load(f)
		badge_labels = labels[BADGES_KEY]
		cargo_labels = labels[CARGOS_KEY]

	for file in os.listdir("grfs"):
		if not file.endswith(".grf"):
			continue
		public, private, hidden, id, strings, cargos, cargo_strings, rrtt, rrtt_strings = read_grf_file(os.path.join("grfs", file), DEBUG)

		date = find_grf_date(id, DEBUG)
		for label in public:
			if label not in badge_labels:
				badge_labels[label] = [id, date.year, date.month, date.day, "", 0, ""]
		for label in private:
			if label not in badge_labels:
				badge_labels[label] = [id, date.year, date.month, date.day, "", (1 << LabelFlags.Private), ""]
		for label in cargos:
			if label not in cargo_labels:
				cargo_labels[label] = [id, date.year, date.month, date.day, "", 0, ""]
		for feature in rrtt:
			key = rrtt_feature_to_key(feature)
			for label in rrtt[feature]:
				if label not in labels[key]:
					labels[key][label] = [id, date.year, date.month, date.day, "", 0, ""]
		for label in strings.keys():
			if badge_labels[label][6] == "" or badge_labels[label][0] == id:  # GRF can comment on badges without comment and ones that it had introduced.
				badge_labels[label][6] = strings[label]
		for label in cargo_strings.keys():
			if cargo_labels[label][6] == "" or cargo_labels[label][0] == id:  # GRF can comment on cargo labels without comment and ones that it had introduced.
				cargo_labels[label][6] = cargo_strings[label]
		for feature in rrtt_strings:
			key = rrtt_feature_to_key(feature)
			for label in rrtt_strings[feature].keys():
				if label not in labels[key]:
					continue
				if labels[key][label][6] == "" or labels[key][label][0] == id:
					labels[key][label][6] = rrtt_strings[feature][label]

		uses = {BADGES_KEY: sorted(set(public + private + hidden)), CARGOS_KEY: cargos, **{rrtt_feature_to_key(f): sorted(set(rrtt[f])) for f in rrtt}}
		with open(os.path.join("uses", f"{hex(id)[2:]}.yaml"), "w") as uses_x:
			yaml.dump(uses, uses_x)

	with open("labels.yaml", "w") as f:
		yaml.dump(labels, f)

	for key in [BADGES_KEY, CARGOS_KEY, RAIL_KEY, ROAD_KEY, TRAM_KEY]:
		add_uses_to_labels(labels[key], key, DEBUG)

	generate_markdown_page(create_hierarchy(badge_labels, {LabelFlags.Private: 0, LabelFlags.AgingBadly: 0}, DEBUG), os.path.join(BADGES_KEY, "public_labels"), DEBUG)
	generate_markdown_page(create_hierarchy(badge_labels, {LabelFlags.Private: 1, LabelFlags.AgingBadly: 0}, DEBUG), os.path.join(BADGES_KEY, "private_labels"), DEBUG)
	generate_markdown_page(create_hierarchy(badge_labels, {LabelFlags.AgingBadly: 1}, DEBUG), os.path.join(BADGES_KEY, "aging_badly_labels"), DEBUG)

	generate_markdown_page(create_hierarchy(cargo_labels, {LabelFlags.AgingBadly: 0}, DEBUG, False), os.path.join(CARGOS_KEY, "public_labels"), DEBUG, ["Classes"])
	generate_markdown_page(create_hierarchy(cargo_labels, {LabelFlags.AgingBadly: 1}, DEBUG, False), os.path.join(CARGOS_KEY, "aging_badly_labels"), DEBUG, ["Classes"])

	rrtt_hierarchy = {
		"Rail Types": create_hierarchy(labels[RAIL_KEY], {LabelFlags.AgingBadly: 0}, DEBUG, False)["Labels"],
		"Road Types": create_hierarchy(labels[ROAD_KEY], {LabelFlags.AgingBadly: 0}, DEBUG, False)["Labels"],
		"Tram Types": create_hierarchy(labels[TRAM_KEY], {LabelFlags.AgingBadly: 0}, DEBUG, False)["Labels"],
	}
	generate_markdown_page(rrtt_hierarchy, os.path.join("rail_road_tram_types", "public_labels"), DEBUG)

	rrtt_hierarchy = {
		"Rail Types": create_hierarchy(labels[RAIL_KEY], {LabelFlags.AgingBadly: 1}, DEBUG, False)["Labels"],
		"Road Types": create_hierarchy(labels[ROAD_KEY], {LabelFlags.AgingBadly: 1}, DEBUG, False)["Labels"],
		"Tram Types": create_hierarchy(labels[TRAM_KEY], {LabelFlags.AgingBadly: 1}, DEBUG, False)["Labels"],
	}
	generate_markdown_page(rrtt_hierarchy, os.path.join("rail_road_tram_types", "aging_badly_labels"), DEBUG)
