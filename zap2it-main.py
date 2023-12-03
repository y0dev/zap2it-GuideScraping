import configparser
import urllib.parse
import requests
import time, datetime
import xml.dom.minidom
import sys, os, argparse

class Zap2It():

    def __init__(self,configLocation="./zap2itconfig.ini",outputFile="xmlguide.xmltv"):
        self.confLocation = configLocation
        self.outputFile=outputFile
        print("Loading config: ", self.confLocation, " and outputting: ", outputFile)
        self.config = configparser.ConfigParser()
        self.config.read(self.confLocation)
        self.lang = self.config.get("prefs","lang")
        self.zapToken = ""
    def BuildAuthRequest(self):
        url = "https://tvlistings.zap2it.com/api/user/login"
        parameters = {
            "emailid": self.config.get("creds","username"),
            "password": self.config.get("creds","password"),
            # "isfacebookuser": "false",
            # "usertype": 0,
            # "objectid": ""
        }
        p_data = urllib.parse.urlencode(parameters).encode()
        return (url, parameters, p_data)
    
    def Authenticate(self):
        #Get token from login form
        authRequest = self.BuildAuthRequest()
        resp = requests.post(authRequest[0],data=authRequest[1])
        if resp.status_code != 200:
            print(f'Failed Authentication: {resp.status_code}')
            print(authRequest[0],authRequest[1])
            exit(-1)

        print('Auth response finished')
        authFormVars = resp.json()
        self.zapToken = authFormVars["token"]
        self.headendid= authFormVars["properties"]["2004"]

    def BuildIDRequest(self):
        url = "https://tvlistings.zap2it.com/gapzap_webapi/api/Providers/getPostalCodeProviders/"
        url += self.config.get("prefs","country") + "/"
        url += self.config.get("prefs","zipCode") + "/gapzap/"
        if self.config.has_option("prefs","lang"):
            url += self.config.get("prefs","lang")
        else:
            url += "en-us"

        resp = requests.post(url)
        if resp.status_code != 200:
            print(f'Failed Build Id Request: {resp.status_code}')
            print(url)
            exit(-1)
        return url
            
    def FindID(self):
        idRequest = self.BuildIDRequest()
        resp = requests.get(idRequest)
        if resp.status_code != 200:
            print(f'Failed to find id: {resp.status_code}')
            print(idRequest)
            exit(-1)

        idVars = resp.json()
        # print(idVars)
        print(f'{"type":<15}|{"name":<40}|{"location":<15}|',end='')
        print(f'{"headendID":<15}|{"lineupId":<25}|{"device":<15}')
        for provider in idVars["Providers"]:
            print(f'{provider["type"]:<15}|',end='')
            print(f'{provider["name"]:<40}|',end='')
            print(f'{provider["location"]:<15}|',end='')
            print(f'{provider["headendId"]:<15}|',end='')
            print(f'{provider["lineupId"]:<25}|',end='')
            print(f'{provider["device"]:<15}')

    def BuildDataRequest(self,currentTime):
        #Defaults
        lineupId = self.headendid
        headendId = 'lineupId'
        device = '-'


        if self.config.has_option("lineup","lineupId"):
            lineupId = self.config.get("lineup","lineupId")
        if self.config.has_option("lineup","headendId"):
            headendId = self.config.get("lineup","headendId")
        if self.config.has_option("lineup","device"):
            device = self.config.get("lineup","device")

        parameters = {
            'Activity_ID': 1,
            'FromPage': "TV%20Guide",
            'AffiliateId': "gapzap",
            'token': self.zapToken,
            'aid': 'gapzap',
            'lineupId': lineupId,
            'timespan': 3,
            'headendId': headendId,
            'country': self.config.get("prefs", "country"),
            'device': device,
            'postalCode': self.config.get("prefs", "zipCode"),
            'isOverride': "true",
            'time': currentTime,
            'pref': 'm,p',
            'userId': '-'
        }
        data = urllib.parse.urlencode(parameters)
        url = "https://tvlistings.zap2it.com/api/grid?" + data
        return url
    
    def GetData(self,time):
        request = self.BuildDataRequest(time)
        print("Load Guide for time: ",str(time))
        resp = requests.get(request)
        if resp.status_code != 200:
            print(f'Failed to get data: {resp.status_code}')
            print(request)
            exit(-1)
        return resp.json()
    
    def AddChannelsToGuide(self, json):
        for channel in json["channels"]:
            self.rootEl.appendChild(self.BuildChannelXML(channel))

    def AddEventsToGuide(self,json):
        for channel in json["channels"]:
            for event in channel["events"]:
                self.rootEl.appendChild(self.BuildEventXmL(event,channel["channelId"]))

    def BuildEventXmL(self,event,channelId):
        #preConfig
        season = "0"
        episode = "0"

        programEl = self.guideXML.createElement("programme")
        programEl.setAttribute("start",self.BuildXMLDate(event["startTime"]))
        programEl.setAttribute("stop",self.BuildXMLDate(event["endTime"]))
        programEl.setAttribute("channel",channelId)

        titleEl = self.guideXML.createElement("title")
        titleEl.setAttribute("lang",self.lang) #TODO: define
        titleTextEl = self.guideXML.createTextNode(event["program"]["title"])
        titleEl.appendChild(titleTextEl)
        programEl.appendChild(titleEl)

        if event["program"]["episodeTitle"] is not None:
            subTitleEl = self.CreateElementWithData("sub-title",event["program"]["episodeTitle"])
            subTitleEl.setAttribute("lang",self.lang)
            programEl.appendChild(subTitleEl)

        if event["program"]["shortDesc"] is None:
            event["program"]["shortDesc"] = "Unavailable"
        descriptionEl = self.CreateElementWithData("desc",event["program"]["shortDesc"])
        descriptionEl.setAttribute("lang",self.lang)
        programEl.appendChild(descriptionEl)

        lengthEl = self.CreateElementWithData("length",event["duration"])
        lengthEl.setAttribute("units","minutes")
        programEl.appendChild(lengthEl)

        if event["thumbnail"] is not None:
            thumbnailEl = self.CreateElementWithData("thumbnail","http://zap2it.tmsimg.com/assets/" + event["thumbnail"] + ".jpg")
            programEl.appendChild(thumbnailEl)
            iconEl = self.guideXML.createElement("icon")
            iconEl.setAttribute("src","http://zap2it.tmsimg.com/assets/" + event["thumbnail"] + ".jpg")
            programEl.appendChild(iconEl)


        urlEl = self.CreateElementWithData("url","https://tvlistings.zap2it.com//overview.html?programSeriesId=" + event["seriesId"] + "&amp;tmsId=" + event["program"]["id"])
        programEl.appendChild(urlEl)
        #Build Season Data
        try:
            if event["program"]["season"] is not None:
                season = str(event["program"]["season"])
            if event["program"]["episode"] is not None:
                episode = str(event["program"]["episode"])
        except KeyError:
            print("No Season for:" + event["program"]["title"])

        for category in event["filter"]:
            categoryEl = self.CreateElementWithData("category",category.replace('filter-',''))
            categoryEl.setAttribute("lang",self.lang)
            programEl.appendChild(categoryEl)

        if((int(season) != 0) and (int(episode) != 0)):
            categoryEl = self.CreateElementWithData("category","Series")
            programEl.appendChild(categoryEl)
            episodeNum =  "S" + str(event["seriesId"]).zfill(2) + "E" + str(episode.zfill(2))
            episodeNumEl = self.CreateElementWithData("episode-num",episodeNum)
            episodeNumEl.setAttribute("system","common")
            programEl.appendChild(episodeNumEl)
            episodeNum = str(int(season)-1) + "." +str(int(episode)-1)
            episodeNumEl = self.CreateElementWithData("episode-num",episodeNum)
            programEl.appendChild(episodeNumEl)

        if event["program"]["id"[-4:]] == "0000":
            episodeNumEl = self.CreateElementWithData("episode-num",event["seriesId"] + '.' + event["program"]["id"][-4:])
            episodeNumEl.setAttribute("system","dd_progid")
        else:
            episodeNumEl = self.CreateElementWithData("episode-num",event["seriesId"].replace('SH','EP') + '.' + event["program"]["id"][-4:])
            episodeNumEl.setAttribute("system","dd_progid")
        programEl.appendChild(episodeNumEl)

        #Handle Flags
        for flag in event["flag"]:
            if flag == "New":
                programEl.appendChild(self.guideXML.createElement("New"))
            if flag == "Finale":
                programEl.appendChild(self.guideXML.createElement("Finale"))
            if flag == "Premiere":
                programEl.appendChild(self.guideXML.createElement("Premiere"))
        if "New" not in event["flag"]:
            programEl.appendChild(self.guideXML.createElement("previously-shown"))
        for tag in event["tags"]:
            if tag == "CC":
                subtitlesEl = self.guideXML.createElement("subtitle")
                subtitlesEl.setAttribute("type","teletext")
                programEl.appendChild(subtitlesEl)
        if event["rating"] is not None:
            ratingEl = self.guideXML.createElement("rating")
            valueEl = self.CreateElementWithData("value",event["rating"])
            ratingEl.appendChild(valueEl)
        return programEl
    
    def BuildXMLDate(self,inTime):
        output = inTime.replace('-','').replace('T','').replace(':','')
        output = output.replace('Z',' +0000')
        return output
    
    def BuildChannelXML(self,channel):
        channelEl = self.guideXML.createElement('channel')
        channelEl.setAttribute('id',channel["channelId"])
        dispName1 = self.CreateElementWithData("display-name",channel["channelNo"] + " " + channel["callSign"])
        dispName2 = self.CreateElementWithData("display-name",channel["channelNo"])
        dispName3 = self.CreateElementWithData("display-name",channel["callSign"])
        dispName4 = self.CreateElementWithData("display-name",channel["affiliateName"].title())
        iconEl = self.guideXML.createElement("icon")
        iconEl.setAttribute("src","http://"+(channel["thumbnail"].partition('?')[0] or "").lstrip('/'))
        channelEl.appendChild(dispName1)
        channelEl.appendChild(dispName2)
        channelEl.appendChild(dispName3)
        channelEl.appendChild(dispName4)
        channelEl.appendChild(iconEl)
        return channelEl

    def CreateElementWithData(self,name,data):
        el = self.guideXML.createElement(name)
        elText = self.guideXML.createTextNode(data)
        el.appendChild(elText)
        return el
    
    def GetGuideTimes(self):
        currentTimestamp = time.time()
        currentTimestamp -= 60 * 60 * 24
        halfHourOffset = currentTimestamp % (60 * 30)
        currentTimestamp = currentTimestamp - halfHourOffset
        endTimeStamp = currentTimestamp + (60 * 60 * 336)
        return (currentTimestamp,endTimeStamp)
    
    def BuildRootEl(self):
        self.rootEl = self.guideXML.createElement('tv')
        self.rootEl.setAttribute("source-info-url","http://tvlistings.zap2it.com/")
        self.rootEl.setAttribute("source-info-name","zap2it")
        self.rootEl.setAttribute("generator-info-name","zap2it-GuideScraping)")
        self.rootEl.setAttribute("generator-info-url","devdoesit17@gmail.com")
    
    def BuildGuide(self):
        self.Authenticate()
        self.guideXML = xml.dom.minidom.Document()
        print('guideXML finished')
        impl = xml.dom.minidom.getDOMImplementation()
        print('impl finished')
        doctype = impl.createDocumentType("tv","","xmltv.dtd")
        print('doctype finished')
        self.guideXML.appendChild(doctype)
        self.BuildRootEl()

        addChannels = True;
        times = self.GetGuideTimes()
        # print(f'guide times {times}')
        loopTime = times[0]
        while(loopTime < times[1]):
            json = self.GetData(loopTime)
            # print(f'json {json}')
            if addChannels:
                self.AddChannelsToGuide(json)     
                addChannels = False           
            self.AddEventsToGuide(json)
            loopTime += (60 * 60 * 3)
        self.guideXML.appendChild(self.rootEl)
        self.WriteGuide()

        print('write guide finished')
        self.CopyHistorical()
        self.CleanHistorical()

    def WriteGuide(self):
        with open(self.outputFile,"wb") as file:
            file.write(self.guideXML.toprettyxml().encode("utf8"))
            
    def CopyHistorical(self):
        dateTimeObj = datetime.datetime.now()
        timestampStr = "." + dateTimeObj.strftime("%Y%m%d%H%M%S") + '.xmltv'
        histGuideFile = timestampStr.join(optGuideFile.rsplit('.xmltv',1))
        with open(histGuideFile,"wb") as file:
            file.write(self.guideXML.toprettyxml().encode("utf8"))

    def CleanHistorical(self):
        outputFilePath = os.path.abspath(self.outputFile)
        outputDir = os.path.dirname(outputFilePath)
        for item in os.listdir(outputDir):
            fileName = os.path.join(outputDir,item)
            if os.path.isfile(fileName) & item.endswith('.xmltv'):
                histGuideDays = self.config.get("prefs","historicalGuideDays")
                if os.stat(fileName).st_mtime < int(histGuideDays) * 86400:
                    os.remove(fileName)



#Run the Scraper
optConfigFile = './zap2itconfig.ini'
optGuideFile = 'xmlguide.xmltv'
optLanguage = 'en'

parser = argparse.ArgumentParser("Parse Zap2it Guide into XMLTV")
parser.add_argument("-c","--configfile","-i","--ifile", help='Path to config file')
parser.add_argument("-o","--outputfile","--ofile", help='Path to output file')
parser.add_argument("-l","--language", help='Language')
parser.add_argument("-f","--findid", action="store_true", help='Find Headendid / lineupid')

args = parser.parse_args()
print(args)
if args.configfile is not None:
    optConfigFile = args.configfile
if args.outputfile is not None:
    optGuideFile = args.outputfile
if args.language is not None:
    optLanguage = args.language

guide = Zap2It(optConfigFile,optGuideFile)
if optLanguage != "en":
    guide.lang = optLanguage

if args.findid is not None and args.findid:
    #locate the IDs
    guide.FindID()
    sys.exit()

dateTimeObj = datetime.datetime.now()
print(f'Running {dateTimeObj.strftime("%m/%d/%Y-%H:%M:%S")}')

guide.BuildGuide()


