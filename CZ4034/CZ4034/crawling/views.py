from django.shortcuts import render,redirect
import tweepy
import json
import solr
from urllib2 import *
from datetime import datetime
from CZ4034.settings import *
from Classification import *

#Store the trained classifier
train_count_vector=""
classifier=""

#Home page
def home(request,source="",category="",sort="",page=""):

    #News Source
    request.session.source_list = {"Straits Times":"37874853","BBC":"742143","Wall Streets Journal":"3108351","CNN":"759251","New York Times":"807095"}

    #connect to Twitter
    auth = tweepy.OAuthHandler('f11IQFNPOQuaopvynNXCjGrF3','ZwTx5EbMhjP4uDTktVINZF5E25bFjKEKWXNihiQPbzmjDg9j3S')
    auth.set_access_token('827805611865747456-WO1lplOfxP4NPMZUTOczxN3IyVz7vDc','ebekAEeMEsKRCtN5WvgMN9r4eoURI39Q0PumL2zyXelsA')
    api = tweepy.API(auth)

    #Connect to Solr
    connection = solr.SolrConnection('http://localhost:8983/solr/CZ4034',debug=True)

    #Check whether user has specify any particular new sources or categories
    if not source:
        source = "All2"
    if not category:
        category="All"

    if source != "All2":
        if category !="All":
            status_list = connection.query('name:'+source+' AND category:'+category,rows = 100,sort = "time desc").results
        else:
            status_list = connection.query('name:' + source,rows = 100,sort = "time desc").results
    else:
        if category !="All":
            status_list = connection.query('category:' + category,rows = 100,sort = "time desc").results
        else:
            status_list = connection.query('*:*',rows = 100,sort = "time desc").results

    #Get Retweet count for each tweet
    for status in status_list:
        status["retweet_count"] = status["retweet_count"][0]

    #Sort the tweets based on user's choice
    if sort=="Popularity":
        status_list = sorted(status_list,key=lambda status_list: status_list["like"],reverse = True)
    elif sort=="Retweet":
        status_list = sorted(status_list,key=lambda status_list: status_list["retweet_count"],reverse = True)
    else:
        status_list = sorted(status_list,key=lambda status_list: status_list["time"],reverse = True)

    #Store the tweets in sessions
    request.session.status_list = status_list

    #Get the number of pages to be displayed
    pages = getPage(request)

    #If zero tweets are retrieved, the page is one
    if not page:
        page = 1

    #Get the tweets which are separated in pages
    request.session.status_list = getStatusList(status_list,page)

    return render(request,'home2.html',{'status_list':request.session.status_list,'source':source,'category':category,'pages':pages,'sort':sort})

#This is an old function which is used to crawl data from Twitter without classification
#This function is not used any more
def CrawlData(request,api,connection):

    #Delete all documents on Solr first
    connection.delete_query("*:*")
    last_id_dict = {}

    #Get tweets from all resources
    #Use two for loops because the maximum tweets can be retrieved from Twitter is 200 for each query
    for source in request.session.source_list:
        status_list = api.user_timeline(id=request.session.source_list[source],count =200 )
        PostToSolr(status_list,connection)
        last_id_dict[source]=int(status_list[-1]._json["id"])

    for source in request.session.source_list:
        for i in range(0,11):
            status_list = api.user_timeline(id=request.session.source_list[source],count=200,max_id=str(last_id_dict[source]-1))
            PostToSolr(status_list,connection)
            last_id_dict[source]=int(status_list[-1]._json["id"])

#Preprocess Twitter data and store in Solr
def PostToSolr(status_list,connection):
    for status_json in status_list:

        #Get created date
        date_list = status_json["created_at"].split(" ")
        year = date_list[-1]
        time = date_list[3]
        day = date_list[2]
        month = datetime.strptime(date_list[1],"%b").month

        #Get the account's profile image
        profile_image = status_json["user"]["profile_image_url_https"]

        #Get image in tweet if there is any
        if "retweeted_status" in status_json  and "media" in status_json["retweeted_status"]["entities"]:
            tweet_image = status_json["retweeted_status"]["entities"]["media"][0]["media_url_https"]
        else:
            tweet_image = "no image"

        #Get number of retweets for each tweet
        retweet_count = status_json["retweet_count"]

        #Format the month
        if month<10:
            month = "0"+str(month)

        #Store the tweet in Solr
        connection.add(category = status_json["category"],content_raw = status_json["text"],tweet_image = tweet_image,retweet_count = retweet_count,profile_image=profile_image,id=status_json["id_str"],time=str(year)+"-"+str(month)+"-"+str(day)+"T"+time+"Z",like = status_json["favorite_count"],content=status_json["text"],name=status_json["user"]["screen_name"])

    #Commit after all tweets are stored in Solr
    connection.commit()

#User type keywords or phrases to search
def search(request,category,source,search_value,sort="",page=""):

    #Some preprocess on the search input by user
    search_value = search_value.replace("%20"," ")
    search_value_raw = search_value
    search_value = search_value.lower()

    #Connect to Solr
    connection = solr.SolrConnection('http://localhost:8983/solr/CZ4034',debug=True)

    #Check whether there is any category or new sources specify by user
    if source == "All2":
        if category != "All":
            status_list = connection.query('content:"' + search_value + '" AND category:'+category, rows=100, sort="time desc").results
        else:
            status_list = connection.query('content:"'+search_value +'"',rows=100,sort="time desc").results
    else:
        if category != "All":
            status_list = connection.query('content:"' + search_value + '"' + ' AND name:' + source+' AND category:'+category, rows=100,sort="time desc").results
        else:
            status_list = connection.query('content:"'+search_value+'"'+' AND name:'+source,rows=100,sort="time desc").results

    #Get spellcheck and suggestion from Solr
    conn = urlopen('http://localhost:8983/solr/CZ4034/suggest?q='+search_value.replace(" ","%20")+'&wt=json')
    suggestion_json = json.load(conn)["spellcheck"]["collations"]
    temp_suggestion_list = []
    if len(suggestion_json)>1:
        temp_suggestion_list.append(suggestion_json[1])
    suggestion_list=temp_suggestion_list

    #Get retweet counts
    for status in status_list:
        status["retweet_count"] = status["retweet_count"][0]

    #Check whether user has specified an order for tweets display
    if sort=="Popularity":
        status_list = sorted(status_list,key=lambda status_list: status_list["like"],reverse = True)
    elif sort=="Retweet":
        status_list = sorted(status_list,key=lambda status_list: status_list["retweet_count"],reverse = True)
    else:
        status_list = sorted(status_list,key=lambda status_list: status_list["time"],reverse = True)

    #Same process in 'home' function
    request.session.status_list = status_list
    pages = getPage(request)
    request.session.status_list = getStatusList(status_list,page)
    return render(request,'home2.html',{'sort':sort,'status_list':request.session.status_list,'search_value':search_value_raw,'source':source,'category':category,'suggestion_list':suggestion_list,'pages':pages})

#Get totally number of pages
#Each page contains maximum 10 tweets
def getPage(request):
    length = len(request.session.status_list)/10+1
    if length>10:
        length = 10
    length = range(1,length+1)
    return length

#Ensure pages are displayed correctly
def getStatusList(status_list,page):
    page = int(page)
    length = len(status_list)
    if (length < page*10):
        return status_list[(page-1)*10:length]
    else:
        return status_list[(page-1)*10:page*10]

#Update tweets
def crawlNewData(request):

    #Trained Model
    global train_count_vector
    global classifier


    source_list2 = {"STcom":"37874853","BBCWorld":"742143","WSJ":"3108351","CNN":"759251","nytimes":"807095"}

    #Train the classifier if the classifier has not been created
    if "classifier" not in request.session:
        result_list = get_classifier()
        train_count_vector = result_list[0]
        classifier  = result_list[1]

    if request.method == "POST":

        #Update tweets based on new sources chosen by user
        account_list = request.POST.getlist('account_list[]')
        connection = solr.SolrConnection('http://localhost:8983/solr/CZ4034',debug=True)
        auth = tweepy.OAuthHandler('f11IQFNPOQuaopvynNXCjGrF3','ZwTx5EbMhjP4uDTktVINZF5E25bFjKEKWXNihiQPbzmjDg9j3S')
        auth.set_access_token('827805611865747456-WO1lplOfxP4NPMZUTOczxN3IyVz7vDc','ebekAEeMEsKRCtN5WvgMN9r4eoURI39Q0PumL2zyXelsA')
        api = tweepy.API(auth)
        last_id_dict = {}

        #Update tweets by new sources
        for account in account_list:
            connection.delete_query("name:"+account)
            status_list_raw = api.user_timeline(id=source_list2[account],count =200 )
            status_list=[]


            for status in status_list_raw:
                status=status._json

                #Get text content from each tweet and classify it into one category
                text = []
                text.append(status["text"])
                status["category"]= predict(text,train_count_vector,classifier)[0]
                status_list.append(status)

            #Store the new tweets
            PostToSolr(status_list,connection)
            last_id_dict[account] = int(status_list[-1]["id"])

        for account in account_list:
            for i in range(0,11):
                status_list_raw = api.user_timeline(id=source_list2[account],count=200,max_id=str(last_id_dict[account]-1))
                status_list = []
                for status in status_list_raw:
                    status = status._json
                    text = []
                    text.append(status["text"])
                    status["category"] = predict(text, train_count_vector, classifier)[0]
                    status_list.append(status)
                PostToSolr(status_list,connection)
                last_id_dict[account] = int(status_list[-1]["id"])

    return redirect('/')