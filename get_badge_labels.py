import os
from datetime import date as Date
import yaml
from decode import int_from_bytes, is_extended_byte_a_word, int_from_extended_byte, read_string


class LabelFlags:
	AgingBadly = 0
	Private = 1


def read_grf_file(file, debug=False):
	"""Parses prowided .grf file and returns 3 arrays of labels: public, private and hidden."""
	# Outputs
	out = []
	private_out = []
	hidden_out = []
	strings = {}
	grf_id = 0
	with open(file, "rb") as f:
		data = f.read()
		badges = {}
		_sprites_start = int_from_bytes(data[10:14])  # Remove leading `_` if used.
		i = 15  # i short for iterator. 15 skips file header of grf format 2.
		size = int_from_bytes(data[i : i + 4])  # Read size of first sprite.
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
					num_of_badges = data[i + 3]  # How many badges are changed by this action 0x00.
					first_badge = int_from_extended_byte(data[i + 4 : i + 7])
					j = i + 4 + (3 if is_extended_byte_a_word(data[i + 4]) else 1)  # Skip to the property number.
					for __p__ in range(props):
						prop = data[j]  # Read what property is set.
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
							for b in range(num_of_badges):
								badges[first_badge + b] = label
						else:
							print("invalid prop:", prop)  # Corruption or newer grf version.
							break  # We don't know how long this property is, therefore we can't read any more properties :(
						j += 1
				elif data[i] == 0x08:  # Maybe it is an action 0x08 instead.
					grf_id = int_from_bytes(data[i + 5 : i + 1 : -1])  # Read grf id.
					if debug:
						print("GRF ID:", hex(grf_id))
				elif data[i] == 0x04 and data[i + 1] == 0x15:  # Might also be text string for badges.
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
						for badge in range(offset, offset + number_of_strings):
							string = read_string(j, data)
							if badge in badges:
								strings[badges[badge]] = string
								if debug:
									print(badges[badge], "\t\t", string)
							j += len(string) + 1  # Text is followed by 0x00 byte.
			i = i + size
			size = int_from_bytes(data[i : i + 4])
	return out, private_out, hidden_out, grf_id, strings


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


def generate_markdown_page(labels, page_name, required_flags: dict, debug=False):
	flags_mask = 0
	flags_values = 0
	for flag in required_flags:
		flags_mask |= 1 << flag
		flags_values |= required_flags[flag] << flag
	labels = dict(labels)
	hierarchy = {-1: None}
	for label in sorted(labels.keys()):
		if labels[label][5] & flags_mask != flags_values:
			continue
		first_slash = label.find("/")
		if first_slash == -1:  # It is a class.
			hierarchy[label] = []
		else:  # It is a normall badge
			class_label = label[:first_slash]
			if class_label not in hierarchy:
				if class_label not in labels:
					if debug:
						print("No class for badge:", label)
					labels[class_label] = [labels[label][0], labels[label][1], labels[label][2], labels[label][3], "AUTO GENERATED CLASS", "0"]
				hierarchy[class_label] = []
			hierarchy[class_label].append(label)
	with open(os.path.join("gen_docs", f"{page_name}.md"), "w") as md_file:
		hierarchy[-1] = list(hierarchy.keys())
		hierarchy[-1].remove(-1)
		for c in hierarchy.keys():
			if c == -1:  # It is a classes table.
				md_file.write("# Classes\n")
			else:  # It is a table for specific class.
				md_file.write("\n# {}\n".format(c))
			md_file.write("| Label | Introduced by | When | Comment | O. |\n")
			md_file.write("| --- | --- | --- | --- | --- |\n")
			for b in hierarchy[c]:
				label = b
				if c == -1:  # It is a classes table.
					label = "[{0}](#{0})".format(b)  # Link to a table for this class.
				grf_id = labels[b][0]
				if grf_id == -1:  # It comes from default badges by Peter Nelson.
					grf_id = "[OpenTTD default badges](https://github.com/OpenTTD/OpenTTD/pull/13655)"
				elif grf_id == -2:  # Introduced by community but not necessarily used in any grfs.
					grf_id = "[Community](https://www.tt-forums.net)"
				else:  # Introduced by grf from BaNaNaS.
					grf_id = "[{0}](https://bananas.openttd.org/package/newgrf/{1})".format(find_grf_name(grf_id, debug), hex(grf_id)[2:])
				when = "{0}-{1:02d}-{2:02d}".format(labels[b][1], labels[b][2], labels[b][3])  # Introduction date.
				comment = labels[b][4] if labels[b][4] else labels[b][6]  # Use string from grf if no comment provided.
				md_file.write("| {0} | {1} | {2} | {3} | {4} |\n".format(label, grf_id, when, comment, labels[b][-1]))


def add_uses_to_labels(labels, key, debug=False):
	start_size = len(labels["flag"])  # Can be any label, `flag` used as it is added by OpenTTD default badges.
	if not os.path.isdir("uses"):
		return
	for file in os.listdir("uses"):
		if file[-5:] != ".yaml":
			continue  # Someone has put invalid file into this directory.
		grf_id = file[:-5]
		with open(os.path.join("uses", file), "r") as f:
			module = yaml.safe_load(f)
		for label in module[key] if isinstance(module, dict) else module:
			if label not in labels:
				continue  # Lable from another scope.
			if len(labels[label]) == start_size:
				labels[label].append([grf_id])
			else:
				labels[label][start_size].append(grf_id)
	for label in labels.keys():
		if len(labels[label]) == start_size:
			labels[label].append("0")
			if labels[label][0] >= 0:
				if debug:
					pass  # print(label, "is aging badly.")
				labels[label][5] |= 1 << LabelFlags.AgingBadly
		else:
			li = sorted(labels[label][start_size])
			labels[label][start_size] = '[{0}](https://bananas.openttd.org/?message=GRFs:+{2} "{1}")'.format(len(li), ", ".join(li), ",+".join(li))


if __name__ == "__main__":
	DEBUG = True
	BADGES_KEY = "badges"
	with open("badge_labels.yaml", "r") as f:
		badge_labels = yaml.safe_load(f)

	for file in os.listdir("grfs"):
		if not file.endswith(".grf"):
			continue
		public, private, hidden, id, strings = read_grf_file(os.path.join("grfs", file), DEBUG)

		date = find_grf_date(id, DEBUG)
		for label in public:
			if label not in badge_labels:
				badge_labels[label] = [id, date.year, date.month, date.day, "", 0, ""]
		for label in private:
			if label not in badge_labels:
				badge_labels[label] = [id, date.year, date.month, date.day, "", (1 << LabelFlags.Private), ""]
		for label in strings.keys():
			if badge_labels[label][6] == "" or badge_labels[label][0] == id:  # GRF can comment on badges without comment and ones that it had introduced.
				badge_labels[label][6] = strings[label]

		uses = {BADGES_KEY: sorted(public + private + hidden)}
		with open(os.path.join("uses", f"{hex(id)[2:]}.yaml"), "w") as uses_x:
			yaml.dump(uses, uses_x)

	with open("badge_labels.yaml", "w") as public_labels:
		yaml.dump(badge_labels, public_labels)

	add_uses_to_labels(badge_labels, BADGES_KEY, DEBUG)  # WARNING: badge_labels is passed by reference.
	generate_markdown_page(badge_labels, "public_labels", {LabelFlags.Private: 0, LabelFlags.AgingBadly: 0}, DEBUG)
	generate_markdown_page(badge_labels, "private_labels", {LabelFlags.Private: 1, LabelFlags.AgingBadly: 0}, DEBUG)
	generate_markdown_page(badge_labels, "aging_badly_labels", {LabelFlags.AgingBadly: 1}, DEBUG)
