# caltopo_show_coverage.py - generate a bitmap showing tile coverage pattern
#  for any directory tree of Caltopo-named mbtiles files;
#  one image will be generated for each layer and detail level (1m/2m/4m/8m);
#  each image will show one pixel per tile file that exists in the proper directory
# TMG 4-19-20 - modified from tms_show_coverage.py

# SYNTAX: caltopo_show_coverage.py <dir>
#  - dir, and/or its subdirectories, must contain caltopo-named mbtiles files
#  - the same directory tree that exists under 'dir' will be created under 'coverage'
#     with an image named <layername>_coverage.png in each leaf directory

# caltopo file name convention:
#  <base>
# Tiles downloaded from sartopo.com are 15-minute-square .mbtiles files with
#  standard filenames, ending with [-scale]-<lat>-<lon>-<qq>.mbtiles:
# - scale is an optional indicator of zoom levels contained in the file,
#     in terms of nominal meters-per-pixel; typically, ‘1m’ means the file
#     contains zoom level 17, ‘2m’ means the file contains zoom level 16,
#     and absence of this indicator means the file contains zoom levels 15
#     and lower; some overlay layers use a different guideline
# - lat and lon are positive integer degrees (in the western hemisphere)
#     indicating the bottom-right (southeast) corner of a 1-by-1 degree block
# - qq is a two-digit subgrid reference within the 1x1-degree block as shown
#
#  +----+----+----+----+
#  | 33 | 32 | 31 | 30 |
#  +----+----+----+----+
#  | 23 | 22 | 21 | 20 |
#  +----+----+----+----+
#  | 13 | 12 | 11 | 10 |
#  +----+----+----+----+
#  | 03 | 02 | 01 | 00 |
#  +----+----+----+----+

# import zipfile
from PIL import Image,ImageColor,ImageChops,ImageDraw,ImageFont
import os
import sys
import re
from sys import stdout
import numpy as np
import glob
import time

def parse_mbtiles_filename(fn):
	# given a caltopo-standard mbtiles filename, return a list
	#  [basename,lat,lon,qy,qx]
	#    basename = everything before the grid name
	#    lat,lon = latitude and longitude in integer-truncated degrees
	#    qy,qx = first and second digits of qq (15-minute-grid code)
	if not fn.endswith(".mbtiles"):
		print("PARSE ERROR: Not an mbtiles file: "+fn)
		return None
	b=fn.replace(".mbtiles","")
	p=b.split("-")
	if len(p)<4:
		print("PARSE ERROR: Not a caltopo standard filename: "+fn)
		return None
	[lat,lon,qq]=p[-3:]
	if not (lat.isdigit() and lon.isdigit() and qq.isdigit()):
		print("PARSE ERROR: The last three tokens must only conatin numbers: "+fn)
		return None
	lat=int(lat)
	lon=int(lon)
	if len(qq)!=2:
		print("PARSE ERROR: The last token must be two digits: "+fn)
		return None
	[qy,qx]=map(int,list(qq))
	if qx not in range(0,4) or qy not in range(0,4):
		print("PARSE ERROR: Each digit of the last token must be between 0 and 3: "+fn)
		return None
	basename="-".join(p[:-3])
	return [basename,lat,lon,qy,qx]
	
# function for use in 'map' below: return filename base (filename minus any extension)
def basename_int (filename):
	return int(os.path.splitext(filename)[0])

# list only directories (not full dir names), modified from
# http://stackoverflow.com/questions/141291/how-to-list-only-top-level-directories-in-python
def listsubdirs(folder):  
	return [
		d for d in os.listdir(folder)
			if os.path.isdir(os.path.join(folder,d))
	]

# allow specific (pre-normalized) boundaries, so that the same image size and location
#  can be used for all layers in all nested directories
# NOTE we want to use the same image size for all basenames, even within the same directory

#   coordinate names:
#     qq,qx,qy = subgrid coordinates (0-3 each) as in the ascii-art above
#     gxy,gx,gy = integer 'grid' x and y: 1 grid = 15'x15'
#     llx,lly = lower-left x and y in pixels
#     urx,ury = upper-right x and y in pixels
#      In the projection used by the caltopo coverage maps,
#      longitude lines are evenly spaced, but, latitude lines are spaced
#      farther apart for higher latutide (farther north).  Calculating the
#      integer pixel height of each grid would result in cumulative
#      rounding error, so, instead, calculate the lly and ury of each grid.

# coefficients for calculating height of a grid in projected pixels
m=0.07317
b=14.63415

gw=27.7778 # width of a grid, in pixels

# first, build a dictionary of grid height (in pixels) as a function of gy
phd={}
for gy in range(-200,1):
	phd[gy]=(-m*gy)+b
	
# print(str(phd))
 	
# now build a floating-point dictionary of py as a function of gy
pyfd={}
pyfd[-200]=-phd[-200]
for gy in range(-199,1):
# 	pyd[gy]=-int(gw*gy*(1+m))
	pyfd[gy]=pyfd[gy-1]-phd[gy]
# 	pyd[gy]=int(gw*((-gy)**(1+m)))

# print(str(pyfd))



# this set of key-value pairs is hand-entered from an arbitrary screenshot of
#   the caltopo offline coverage map.  So, that values are arbitrary, but,
#   the heights are accurate; since y coordinates are normalized later, we can
#   use these exact coordinates for pyd	
k=range(-170,-126)
v=[1299.5,1275.5,1251.0,1226.7,1202.4,1178.1,1153.7,1128.6,1104.4,1079.0,
    1054.8,1029.5,1004.4,980.1,954.7,929.5,904.5,878.3,853.1,827.9,801.8,
    776.7,750.3,724.6,699.2,673.3,647.1,620.1,593.7,567.6,540.7,514.5,487.5,
    461.5,434.4,407.5,380.5,352.5,325.5,298.6,270.5,242.6,215.7,187.7]
# v=[1325,1300,1275,1251,1227,1203,1178,1154,1128,1104,1079,1054,1030,1004,980,955,
#     930,905,878,852,828,802,777,751,725,699,674,648,620,594,568,541,515,488,
#     462,435,408,381,353,326,299,271,243,216,188,160]
pydf=dict(zip(k,v))

# now build the integer dictionary for use when drawing the image
pyd={}
for gy in k:
	pyd[gy]=int(pyfd[gy])
# 	print(str(-pyd[gy]))
	
# print(str(pyd))


def get_coverage(folder,gxmin=None,gxmax=None,gymin=None,gymax=None):
	print("Processing "+folder+"...")
	# basename dictionary: keys = basenames, val = list of gxy coords of files that exist for that basename
	bd={}
	# 1. read files to populate the lists of xy coords
	for fn in (i for i in os.listdir(folder) if i.endswith(".mbtiles")):
		p=parse_mbtiles_filename(fn)
		if p:
			[basename,lat,lon,qy,qx]=p
			if basename not in bd.keys():
				bd[basename]=[]
			gx=-(lon*4+qx) # since (negative latitude) increases leftwards
			gy=-(lat*4+qy) # since image y coordinate increases downwards
			print("p:"+str(p)+" --> "+str(gx)+":"+str(gy))
			bd[basename].append([gx,gy])
	
	# 2. make an image for each basename (note that any -1m or -2m or other size suffix is part of basename)

	for basename in bd.keys():
		coords=bd[basename]
		gxlist=[gxy[0] for gxy in coords]
		gylist=[gxy[1] for gxy in coords]
		gxmin=gxmin or min(gxlist)
		gymin=gymin or min(gylist)
		gxmax=gxmax or max(gxlist)
		gymax=gymax or max(gylist)
	# 	xsize=int((xmax-xmin)*1.1)
	# 	ysize=int((ymax-ymin)*1.1)
		gxsize=gxmax-gxmin+1
		gysize=gymax-gymin+1
		pxsize=int(gxsize*gw)
		pysize=pyd[gymin]-pyd[gymax+1]+3
		pyo=pyd[gymax] # vertical offset in pixels
		print("creating image: "+str(pxsize)+"x"+str(pysize)+"   pyo="+str(pyo))
		img=Image.new('L',(pxsize,pysize),'black')
		pix=img.load()
		gridcount=0
# 		print("coords:"+str(coords))
		for [gx,gy] in coords:
			ngx=gx-gxmin
			gridcount+=1
			llx=int(ngx*gw)
			urx=int((ngx+1)*gw)-1
			lly=pysize-(pyd[gy]-pyo+1)
			ury=pysize-(pyd[gy-1]-pyo)
			print('grid: '+str(gx)+':'+str(gy)+'   box: ll='+str(llx)+':'+str(lly)+'  ur='+str(urx)+':'+str(ury))
			for x in range(llx,urx+1):
				for y in range(ury,lly+1):
					pix[x,y]=164
			for x in range(llx,urx+1):
				pix[x,lly]=128
				pix[x,ury]=128
			for y in range(ury,lly+1):
				pix[llx,y]=128
				pix[urx,y]=128
# 			pix[gx-gxmin,gy-gymin]=128
		img.save(folder+"/"+basename+".bmp")
		print("  total grids: "+str(gridcount))
		
	# 3. recurse subdirectories
	for d in listsubdirs(folder):
		get_coverage(folder+"/"+d,-500,-450,-169,-128)

# call this function after individual coverage maps have been made in subdirectories
def build_top_coverage_maps(topdir):
	# build a list of image files
	imglist=glob.glob(os.path.join(topdir,"**","*.bmp"),recursive=True)
# 	print("image files:"+str(imglist))
	# build dictionary: keys = leaf filenames, vals = list of image files with that leaf name
	imgdict={}
	for imgfile in imglist:
		leafbase=os.path.splitext(os.path.split(imgfile)[-1])[0]
# 		print(leafbase+" : "+imgfile)
		if leafbase in imgdict.keys():
			imgdict[leafbase].append(imgfile)
		else:
			imgdict[leafbase]=[imgfile]
	
	# now build a composite for each dictionary entry
	basemapfile="basemap.png"
	basemap=Image.open(basemapfile)
	compsizeinbasemap=(1160,1208)
	cox=-37
	coy=64
	compositedir="composite"
	if not os.path.isdir(compositedir):
		os.mkdir(compositedir)
	nestcolor=["red","orange","yellow","green","blue","indigo","violet","black"]
	names={
		't':"Scanned 7.5'",
		'c':'Contour Lines',
		'canopy':'Canopy Data',
		'dem8':'Elevation Data',
		'f':'FSTopo 2013',
		'f16a':'FSTopo 2016',
		'mapbuilder_overlay':'MapBuilder Overlay',
		'mapbuilder_topo':'MapBuilder Topo',
		'naip_2014':'NAIP Imagery 2014',
		'nlcd':'Land Cover Data'}
# 	for leafbase in ["t","t-2m"]:
	for leafbase in imgdict.keys():
		compositename=os.path.join(compositedir,leafbase+".png")
		comparray=None
		print("Generating composite image for '"+leafbase+"'")
		for imgfile in imgdict[leafbase]:
			# path split from https://stackoverflow.com/a/16595356/3577105
			s=os.path.normpath(imgfile).split(os.path.sep)
			leafdir=s[-3]
			nestlevel=len(s)-4
			color=nestcolor[nestlevel-1]
			print("  nesting level:"+str(nestlevel)+"  leaf dir:"+str(leafdir))
			img=Image.open(imgfile)
			img=img.convert("RGBA")
			if comparray is None:
				comparray=np.zeros((img.size[1],img.size[0],4),dtype=np.int8)
			pixdata=img.load()
			rgba=ImageColor.getrgb(color)
			if len(rgba)<4:
				rgba=list(rgba)
				rgba.append(255)
				rgba=tuple(rgba)
			for y in range(img.size[1]):
				for x in range(img.size[0]):
					if pixdata[x,y]!=(0,0,0,255):
						comparray[y,x]=rgba
		composite=Image.fromarray(comparray,'RGBA')
		
		# To avoid translucent checkerboards in the resulting image,
		#  we need to use Image.composite instead of image.paste (since paste
		#  also pastes transparency and applies it to the basemap!);
		#  Image.composite does not allow for an offset so we need to create an
		#  overlay and mask with the correct offset, which may be positive or
		#  negative meaning we need to create them with .paste instead of .crop
		compsized=composite.resize(compsizeinbasemap)
		compsizedshifted=Image.new('RGBA',basemap.size,'black')
		compsizedshifted.paste(compsized,(cox,coy,cox+compsized.size[0],coy+compsized.size[1]))
		# make the mask (50% opacity for all non-blank pixels)
		mask=compsizedshifted.copy()
		maskdata=mask.load()
		for y in range(mask.size[1]):
			for x in range(mask.size[0]):
				if maskdata[x,y]!=(0,0,0,0):
					maskdata[x,y]=(255,255,255,128)
		finalcomp=Image.composite(compsizedshifted,basemap,mask)
		
		# add a label
		draw=ImageDraw.Draw(finalcomp)
		fontBig=ImageFont.truetype('C:\\Windows\\Fonts\\ARLRDBD.TTF',40)
		fontSmall=ImageFont.truetype('C:\\Windows\\Fonts\\ARLRDBD.TTF',20)
		layername=re.sub("\-\d+m","",leafbase)
		layertext=names.get(layername,"'"+leafbase+"'")
# 		print("layername='"+layername+"'   layertext="+layertext)
		draw.text((560,160),layertext,(40,40,255),font=fontBig)
		draw.text((580,210),"Filename base: '"+leafbase+"'",(40,40,255),font=fontSmall)
		draw.text((580,235),time.strftime("%b %#d, %Y"),(40,40,255),font=fontSmall)
		finalcomp.save(compositename)

		
topdir=sys.argv[1]	
# get_coverage(topdir)
build_top_coverage_maps(topdir)

print("\nDone.")
