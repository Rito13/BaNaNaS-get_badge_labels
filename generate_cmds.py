GRFS = [
	"16710555",  # Iron Horse 4
	"14893085",  # Polish Stations
	"13751424",  # U&ReRMM 3
	"12786351",  # U&RaTT 2
	"9707458",  # SETS: Narrow gauge
	"15899173",  # SETS: Standard gauge
	"16499692",  # KST SNDTS
]

with open("cmds.txt", "w") as f:
	f.write("\n\n\nhelp\n\n\n")
	f.write("\n" * 10)
	f.write("content update")
	f.write("\n" * 200)
	f.write("content upgrade")
	f.write("\n" * 200)
	f.write("content download")
	f.write("\n" * 1500)
	f.write("exit")
