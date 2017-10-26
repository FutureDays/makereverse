#!/usr/bin/env python
'''
reverses a file
'''
import os
import re
import sys
import argparse
import subprocess

class dotdict(dict):
	'''
	dot.notation access to dictionary attributes
	'''
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__

class cd:
	'''
	Context manager for changing the current working directory
	'''
	def __init__(self, newPath):
		self.newPath = os.path.expanduser(newPath)
	def __enter__(self):
		self.savedPath = os.getcwd()
		os.chdir(self.newPath)
	def __exit__(self, etype, value, traceback):
		os.chdir(self.savedPath)

def process(args):
	count = 0 #init count
	concat = open("concat.txt","w") #init txt file that ffmpeg will parse later
	try:
		while (count < float(args.dur)): #loop through the file 300s at a time until u get to the end
			ffmpegstring = "ffmpeg -i " + args.i + " -ss " + str(count) + " -t 300 -af areverse -acodec pcm_s24le -threads 0 " + os.path.join(args.workingDir,"concat" + str(count) + ".wav")
			output = subprocess.check_output(ffmpegstring)
			concat.write("file concat" + str(count) + ".wav\n") #write it with a newline
			count = count + 300 #incrase seconds by 300 (5min)
		concat.close() #housekeeping
		rtncode = True
	except subprocess.CalledProcessError,e:
		output = e.output
		rtncode = output
	return rtncode

def process_short(args):
	ffmpegstring = "ffmpeg -i " + args.i + " -af areverse -c:a pcm_s24le " + args.i.replace(".wav","-reversed.wav")
	try:
		output = subprocess.check_output(ffmpegstring) #can't stream copy because of -af
		rtncode = True
	except subprocess.CalledProcessError,e:
		rtncode = e.returncode
	return rtncode

def make_ff(args, vargs, streams):
	ffstr = 'blah'
	ff = dotdict({})
	vidcount = 0
	audcount = 0
	for num in streams['numberofstreams']:
		if streams[num+'.codec_type'] == 'video':
			themap = {}
			themap['-pix_fmt:' + str(vidcount)] = streams[num+'.pix_fmt']
			themap['-r:' + str(vidcount)] = streams[num+'.r_frame_rate']
			themap['-s:' + str(vidcount)] = streams[num+'.width'] + 'x' + streams[num+'.height']
			if streams[num+'.codec_name'] == 'jpeg2000':
				themap['-c:v:' + str(vidcount)] = 'libopenjpeg'
			else:
				themap['-c:v:' + str(vidcount)] = streams[num+'.codec_name']
			ff[num] = themap
			vidcount = vidcount + 1
		elif streams[num+'.codec_type'] == 'audio':
			themap = {}
			themap['-c:a:' + str(audcount)] = streams[num+'.codec_name']
			themap['-b:a:' + str(audcount)] = streams[num+'.sample_rate']
			themap['-ac:' + str(audcount)] = streams[num+'.channels']
			ff[num] = themap
			audcount = audcount + 1
	return ff

def make_ffstr(ff, args, vargs, streams):
	ffstr = ''
	ffprefix = 'ffmpeg -i ' + args.i
	maps = '-map 0:v? -map 0:a? -map 0:d? -map_metadata 0 -map_metadata:s:v 0:s:v? -map_metadata:s:a 0:s:a?'
	ffsuffix = '-threads 0 -id3v2_version 3 -write_id3v2 1 -write_bext 1 ' + vargs.endObj
	for stream in streams['numberofstreams']:
		for opts in ff[stream]:
			print opts
			ffstr = ffstr + ' ' + opts + ' ' + ff[stream][opts]

	ffstr = ffprefix + ' ' + maps + ffstr + ' ' + ffsuffix
	print ffstr
	return ffstr

def probe_streams(obj):
	'''
	returns dictionary with each stream element
	e.g. {"0.pix_fmt":"yuv420p10le"}
	'''
	streams = {}
	ffstr = "ffprobe -show_streams -of flat " + obj
	output = subprocess.Popen(ffstr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	_out = output.communicate()
	out = _out[0].splitlines()
	for o in out:
		key, value = o.split("=")
		key = key.replace("streams.stream.","")
		streams[str(key)] = value.replace('"','')
	if streams:
		count = 0
		numberofstreams = []
		for stream in streams:
			if stream[0] in numberofstreams:
				pass
			else:
				numberofstreams.append(str(count))
				count = count + 1
		streams['numberofstreams'] = numberofstreams
		return streams
	else:
		print _out[1]
		return False

def ffgo(ffstr):
	'''
	runs ffmpeg, returns true is success, error is fail
	'''
	try:
		returncode = subprocess.check_output(ffstr)
		returncode = True
	except subprocess.CalledProcessError, e:
		returncode = e.returncode
		print returncode
	return returncode

def get_longest_duration(streams):
	'''
	get the duration of the longest stream
	'''
	if len(streams['numberofstreams']) == 1:
		duration = float(streams['0.duration'])
	else:
		duration = float(streams['0.duration'])
		for stream in streams['numberofstreams']:
			if float(streams[stream + '.duration']) > duration:
				duration = float(streams[stream + '.duration'])
	return duration

def init_args():
	'''
	initialize argument dictionary from command line
	'''
	parser = argparse.ArgumentParser(description="slices, reverses input file, concatenates back together")
	parser.add_argument('-i', '--input', dest='i', help='the path to the file to be reversed')
	parser.add_argument('-o','--output', dest='o', help='the path to the output file, default overwrites input')
	parser.add_argument('-t', '--time', dest='t', type=int, default='100', help='the time in seconds of indv concats')
	return parser.parse_args()

def init_input_validate(args):
	'''
	make sure we can run the thing
	'''
	if not os.path.exists(args.i):
		print "makereverse cannot find the input path supplied"
		sys.exit()
	elif not os.access(os.path.dirname(args.i), os.W_OK):
		print "makereverse needs write permission for " + os.path.dirname(args.i)
		sys.exit()

def init():
	'''
	handles the intialization of the script
	'''
	args = init_args()
	init_input_validate(args)
	streams = probe_streams(args.i)
	vargs = dotdict({})
	if args.o:
		vargs.endObj = args.o
	else:
		vargs.endObj = os.path.basename(args.i)
	vargs.endObjname, vargs.endObjext = os.path.splitext(vargs.endObj)
	vargs.workingDir = os.path.dirname(args.i)
	vargs.duration = get_longest_duration(streams)
	return args, vargs, streams



def main():
	'''
	do the thing
	'''
	args, vargs, streams = init()
	#print streams
	for stream in streams:
		print stream
		print streams[stream]
	with cd(vargs.workingDir):
		if vargs.duration <= args.t:
			print "procshort"
			ffstr = make_ff(args, vargs, streams)
			#revWorked = process_short(args)
		else:
			print "proclong"
			ff = make_ff(args, vargs, streams)
			for f in ff:
				print f
				print ff[f]
			ffstr = make_ffstr(ff, args, vargs, streams)
			worked = ffgo(ffstr)
			'''revWorked = process(args)
			#concatenate the revsered output from slicer loop
			if revWorked is True:
				ffmpegstring = "ffmpeg -f concat -i concat.txt -c:a copy -threads 0 " + endObj + "-reversed.wav"
				try:
					output = subprocess.call(ffmpegstring)
					revWorked = True
				except subprocess.CalledProcessError,e:
					revWorked = e.returncode
		if revWorked is True:
			for f in os.listdir(os.getcwd()):
				match = ''
				match = re.match("concat",f)
				if match:
					os.remove(f)
			if os.path.exists(endObj + "-reversed.wav"):
				if os.path.getsize(endObj.replace(".wav","") + "-reversed.wav") > 50000: #validate that the reversed file is actually good and ok
					if os.path.exists(args.i):
						os.remove(args.i)
						os.rename(endObj + "-reversed.wav", args.i)
		else:
			print "Buddy, there was a problem reversing that file"'''

if __name__ == '__main__':
	main()
