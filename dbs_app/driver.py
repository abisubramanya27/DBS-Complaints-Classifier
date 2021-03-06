# ===================================================================================================== 
""" The Main Function which Integrates the Different Processes  """
# =====================================================================================================

#Importing Python Files we created
import s2t 
import s3_filedownload
import multiple_tarfile_opener
import textsummarization
import calling_comprehend
import upload_s3
import clean_string
import phno_to_accno

#Importing Python Libraries
import json
import os
import boto3
import time

#The s3 object is to be used for clearing the S3 buckets (for future use)
s3 = boto3.resource('s3')

#Number of Test Data
NoT = len([file for file in next(os.walk("./test-audio"))[2] if (file.find("test-audio-") != -1 and file.find(".mp3") != -1)])
#Audio Files should be of the form "test-audio-<number>.mp3"

#Speech to Text - Transcribe Part

def speech_part(bucket_name,filename,path) : 

    #Uploads local audio file to S3 Bucket 
	upload_s3.upload(path,bucket_name,filename)
	time.sleep(20)

	#Utilises Speech to Text from AWS Transcribe  on the S3 audio file and stores the output JSON in S3 Bucket
	filename = s2t.s2t(bucket_name+'/'+filename)
	filename += '.json'

	#Downloads the output JSON of Speech to Text from S3 and stores in Local Storage
	s3_filedownload.download_file(bucket_name,filename)
	time.sleep(20)

	#Clears "audio-complaint" S3 Bucket
	bucket = s3.Bucket('audio-complaint')
	bucket.objects.all().delete()
	time.sleep(20)

	#Gets the Text obtained from the audio, from the JSON file
	input_complaint = ""
	with open("./"+filename) as f:
	       for line in f:
	           data=json.loads(line)
	           input_complaint = data["results"]["transcripts"][0]["transcript"]

	#Deletes the output JSON file downloaded from Local Storage
	os.remove("./"+filename)

	return input_complaint


bucket_name = "audio-complaint"
file_name = "test-audio"        #The name of audio complaint file you wish to process
path = './test-audio/'

input_complaint_list = []
for i in range(NoT) :
	input_complaint_list.append(speech_part(bucket_name,file_name+"-"+str(i+1)+".mp3",path))


#----------------------------------------------------------------------------------------------------------

#Summarization, Cleaning and Classifier Input Generation Part

path = "./"

clean_complaint_list = []
summarized_complaint_list = []

#Summarizes the complaints and cleans it for using the trained model on it
for i in range(NoT) :
	summarized_complaint = textsummarization.summarize(input_complaint_list[i])
	clean_complaint = clean_string.clean(summarized_complaint)
	summarized_complaint_list.append(summarized_complaint)
	clean_complaint_list.append(clean_complaint)

#Writes the cleaned complaints to a .csv file 
with open('./test_complaint.csv','w') as f :
	for i in range(NoT) :
          f.write(clean_complaint_list[i]+'\n')


bucket_name = "complaints-input"
file_name = "test_complaint.csv"

#Uploads the complaint (.csv) file to S3 Bucket
upload_s3.upload(path,bucket_name,file_name)
time.sleep(20)

#----------------------------------------------------------------------------------------------------------

#Complaint Classifier Part

file_name = "output.tar.gz"
bucket_name = "complaintsoutput"
S3_extension = "complaints-input/test_complaint.csv"

#Calls AWS comprehend to classify the complaint
calling_comprehend.comprehend(S3_extension,"ComplaintClassifierv2",bucket_name)

#Downloads the output JSON of Complaints Classifier
s3_filedownload.download_file(bucket_name,file_name)
time.sleep(20)

#Complaints Classification Output from AWS
complaints_json_list = multiple_tarfile_opener.tarfile_open(path+file_name)

#Deletes the output JSON and .tar files from Local Storage
os.remove(path+'predictions.jsonl')
os.remove(path+file_name)

#Clears the "complaintsoutput" S3 Bucket
bucket = s3.Bucket('complaintsoutput')
bucket.objects.all().delete()
time.sleep(20)

#----------------------------------------------------------------------------------------------------------

#Spam Classifier Part

file_name = "output.tar.gz"
bucket_name = "spamoutput"
S3_extension = "complaints-input/test_complaint.csv"

#Calls AWS comprehend to detect if the complaint is spam or not
calling_comprehend.comprehend(S3_extension,"Spamclassifierv2",bucket_name)

#Downloads the output JSON of Spam Classifier
s3_filedownload.download_file(bucket_name,file_name)
time.sleep(20)

#Spam Classification Output from AWS
spam_json_list = multiple_tarfile_opener.tarfile_open(path+file_name)

#Clears the "spamoutput" S3 Bucket
bucket = s3.Bucket('spamoutput')
bucket.objects.all().delete()
time.sleep(30)

#Deletes the output JSON and .tar files from Local Storage
os.remove(path+'predictions.jsonl')
os.remove(path+file_name)

#----------------------------------------------------------------------------------------------------------

#Preparation Part before Outputting to Outputs.txt

#Clears "complaints-input" S3 Bucket
bucket = s3.Bucket('complaints-input')
bucket.objects.all().delete()

#The phone number from which the complaint was registered, which can be tapped
#Here for representative purpose I have assumed a Phone Number
phone_number_list = ["9876543211"]*NoT

#Opening the file to which output will be written
f = open('./Outputs.txt','w')

#----------------------------------------------------------------------------------------------------------

for i in range(NoT) :
	
	f.write("\n\n"+str(i+1)+". ")

	#Outputs if the complaint is spam or not
	f.write("SPAM (YES/NO) : ")
	if(spam_json_list[i][0]['Name'].lower() == "spam") :
		f.write("YES")
	else :
		f.write("NO")

	#------------------------------------------------------------------------------------------------------

	#Outputs the type of complaint
	complaint_type = complaints_json_list[i][0]['Name']
	f.write("\n\nTYPE OF COMPLAINT/QUERY : "+complaint_type)
	f.write("\nOTHER ASSOCIATED COMPLAINT/QUERY TAGS : ")
	other_labels = ""
	count_labels = 0
	for json_obj in complaints_json_list[i] :
		if (json_obj['Name'] == complaint_type) :
			continue
		if(json_obj['Score'] > 0.01) :
			if(count_labels >= 1) :
				other_labels += ', '
			other_labels += json_obj['Name']
			count_labels += 1
		else :
			break

	f.write(other_labels)

	#------------------------------------------------------------------------------------------------------

	#Outputs the summary of complaint
	f.write("\n\nSUMMARY OF COMPLAINT/QUERY : ")
	f.write(summarized_complaint_list[i])

	#Outputs the Phone number and Associated Account numbers
	f.write("\n\nContact Number of the Customer :"+phone_number_list[i])
	f.write("\n"+phno_to_accno.accphmatch(phone_number_list[i]))

	#Outputs the original complaint
	f.write("\n\nORIGINAL COMPLAINT/QUERY : ")
	f.write(input_complaint_list[i])

f.close()

print("\n\nCheck Outputs.txt File")

# ======================================================================================================
