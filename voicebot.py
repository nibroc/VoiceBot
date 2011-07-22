"""

VoiceBot...

A crappy little bot that just voices people who PM it "voiceme"

Ops in the  channel it idles in can message "blockvoice user1 user2..." to
have the bot ignore "voiceme" PMs from those users.  (unblockvoice does the 
inverse)

Additionally, ops can PM it "RAW blah" and <blah> will be sent to back to the
server from the bot (example: "RAW MODE #chan -v nick")


"""

from sys import argv
from os import path
import socket
import pickle

DEBUG_OUTPUT = len(argv) > 1 and argv[1] == "output"

CONFIG = {
	"nick": "VoiceBot",
	"channel": "#somechannel",
	"server": ("somehost", 6667),
	"user": {
		"username": "VoiceBot",
		"hostname": "voice.bot",
		"servername": "my.pony.com.es",
		"realname": "THEY WON'T LET ME STOP VOICING PEOPLE!"
	}
}


def splitPrefix(prefix):
	# If there's no @, assume it's a server name
	if prefix.find("@") == -1:
		return prefix
	
	# nick!user@host
	nickuser, host = prefix.split("@")
	nick, user = nickuser.split("!")
	return (nick, user, host)

# Courtesy of Zigara <3
def parsemsg(s):
	
	"""Breaks a message from an IRC server into its prefix, command, and arguments.
	"""
	
	prefix = ''
	trailing = []
	if not s:
		return False
	if s[0] == ':':
		prefix, s = s[1:].split(' ', 1)
	if s.find(' :') != -1:
		s, trailing = s.split(' :', 1)
		args = s.split()
		args.append(trailing)
	else:
		args = s.split()
	command = args.pop(0)
	return splitPrefix(prefix), command.upper(), args

	
conn = socket.create_connection(CONFIG['server']);

# Woo being too lazy to do line buffering myself!
f = conn.makefile()

# Just throw away the first two lines
# And yes, this horrid hack makes Jesus kill kittens
f.readline()
f.readline()

# NICK name
f.write("NICK %s\n" % CONFIG['nick'])

# USER username hostname servername :Real Name
f.write("USER %s %s %s :%s\n" % (CONFIG['user']['username'], CONFIG['user']['hostname'], CONFIG['user']['servername'], CONFIG['user']['realname']))

f.flush()

voiceIgnore = []
opNicks = []

learned = {}

if path.isfile("learned.db"):
	learnedFile = open("learned.db", "r")
	learned = pickle.load(learnedFile)
	learnedFile.close()
else:
	learnedFile = open("learned.db", "w")
	pickle.dump(learned, learnedFile)
	learnedFile.close()

for line in f:
	line = line.rstrip()
	
	prefix, cmd, args = parsemsg(line)
	
	if DEBUG_OUTPUT:
		print "Prefix: %s || cmd: %s || args: %s" % (prefix, cmd, args)
	
	# Send back a PONG...
	if cmd == "PING":
		f.write("PONG :%s\n" % ' '.join(args))
		f.flush()
	# End of MOTD messages
	elif cmd == "376":
		f.write("JOIN %s\n" % CONFIG['channel'])
		f.flush()
	# 
	elif cmd == "353":
		# args: ['ownnick', '=', '#channel','nick1 nick2 nick3']
		channel = args[2]
		nicks = args[3].split(' ')
		for n in nicks:
			if n.find("@") == 0:
				# User is an op...
				opNick = n[1:]
				if opNick not in opNicks:
					opNicks.append(opNick.lower())
	elif cmd == "JOIN":
		# Someone joined...
		pass
	elif cmd == "PART":
		# Someone parted
		partNick, partUser, partHost = prefix
		if partNick.lower() in opNicks:
			opNicks.remove(partNick.lower())
	elif cmd == "QUIT":
		# Someone quit
		partNick, partUser, partHost = prefix
		if partNick.lower() in opNicks:
			opNicks.remove(partNick.lower())
		pass
	elif cmd == "MODE":
		# Have to make sure it's not a global mode on the nick (on the bot)
		channel = args[0]
		if channel.lower() == CONFIG['channel'].lower():
			# Note: the mode handling is a bit... stupid :p
			mode = args[1]
			if(len(args) > 2):
				modeNick = args[2]
				if mode == "+o":
					# Nick was opped
					if not modeNick.lower() in opNicks:
						opNicks.append(modeNick.lower())
				elif mode == "-o":
					# Nick was deopped >.<
					if modeNick.lower() in opNicks:
						opNicks.remove(modeNick.lower())
	elif cmd == "PRIVMSG":
		# Someone messages...
		msgNick, msgUser, msgHost = prefix
		target = args[0]
		msg = args[1]
		if target == CONFIG['nick']:
			# Private message to bot
			if msg == "voiceme":
				if not msgNick.lower() in voiceIgnore:
					f.write("MODE %s +v %s\n" % (CONFIG['channel'], msgNick))
					f.write("PRIVMSG %s :%s\n" % (msgNick, "You done been voiced"))
					f.flush()
				else:
					f.write("PRIVMSG %s :%s\n" % (msgNick, "You've been banned from being voiced!"))
					f.flush()
			
			# Op only commands...
			if msgNick.lower() in opNicks:
				# Add a user to the blocked voice list
				if msg.find("blockvoice ") == 0:
					nicks = msg[len("blockvoice "):].split(' ')
					for n in nicks:
						f.write("MODE %s -v %s\n" % (CONFIG['channel'], n))
						if not n.lower() in voiceIgnore:
							voiceIgnore.append(n.lower())
							f.write("PRIVMSG %s :%s\n" % (msgNick, "Added %s to the ignore list" % n))
						f.flush()
				
				# Remove a user from the blocked voice list
				if msg.find("unblockvoice ") == 0:
					nicks = msg[len("unblockvoice "):].split(' ')
					for n in nicks:
						if n.lower() in voiceIgnore:
							voiceIgnore.remove(n.lower())
					
						f.write("PRIVMSG %s :%s\n" % (msgNick, "Removed from voice block list: " + ' '.join(nicks)))
						f.flush()
				
				if msg.lower().find("raw ") == 0:
					cmd = msg[len("raw "):]
					f.write(cmd + "\n")
					f.flush()
				
				if msg == "debug":
					f.write("PRIVMSG %s :%s\n" % (msgNick, "Operators: " + ' '.join(opNicks)))
					f.write("PRIVMSG %s :%s\n" % (msgNick, "Voice banned: " + ' '.join(voiceIgnore)))
					f.flush()
					
		else:
			# Message to a channel
			
			# Allow ops to !learn things to the bot
			# Note: learn and replace are the same thing (append doesn't exist)
			
			flushLearned = False
			
			if (msg.find("!learn ") == 0 or msg.find("!replace ") == 0) and msgNick.lower() in opNicks:
				sp = msg.split(' ')
				if(len(sp) >= 3):
					key = sp[1]
					val = ' '.join(sp[2:])
					learned[key] = val
					flushLearned = True
			
			elif msg.find("!forget ") == 0 and msgNick.lower() in opNicks:
				key = msg[len("!forget "):]
				if learned.has_key(key):
					del learned[key]
					flushLearned = True
					
			elif msg.find("? ") == 0:
				key = msg[len("? "):]
				if learned.has_key(key):
					f.write("PRIVMSG %s :%s\n" % (target, "\x02%s\x02: %s" % (key, learned[key])))
				else:
					f.write("PRIVMSG %s :%s\n" % (target, "I don't know \x02%s\x02" % key))
					
				f.flush()
			
			if flushLearned:
				learnedFile = open("learned.db", "w")
				pickle.dump(learned, learnedFile)
			