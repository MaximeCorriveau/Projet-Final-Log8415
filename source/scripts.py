# Setup Hadoop and Spark
My_SQL_script = '''#!/bin/bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip default-jdk wget scala git
sudo apt-get install -y  mysql-server 
cd /home/ubuntu
wget https://downloads.mysql.com/docs/sakila-db.zip
unzip sakila-db.zip


'''

# 4.4 Who wins ?
# Download the following text files from the Gutenberg project
benchmark_datasets= '''#!/bin/bash
wget https://www.gutenberg.ca/ebooks/buchanj-midwinter/buchanj-midwinter-00-t.txt # buchanj-midwinter-00-t.txt
wget https://www.gutenberg.ca/ebooks/carman-farhorizons/carman-farhorizons-00-t.txt # carman-farhorizons-00-t.txt
wget https://www.gutenberg.ca/ebooks/colby-champlain/colby-champlain-00-t.txt # colby-champlain-00-t.txt
wget https://www.gutenberg.ca/ebooks/cheyneyp-darkbahama/cheyneyp-darkbahama-00-t.txt # cheyneyp-darkbahama-00-t.txt
wget https://www.gutenberg.ca/ebooks/delamare-bumps/delamare-bumps-00-t.txt # delamare-bumps-00-t.txt
wget https://www.gutenberg.ca/ebooks/charlesworth-scene/charlesworth-scene-00-t.txt # charlesworth-scene-00-t.txt
wget https://www.gutenberg.ca/ebooks/delamare-lucy/delamare-lucy-00-t.txt # delamare-lucy-00-t.txt
wget https://www.gutenberg.ca/ebooks/delamare-myfanwy/delamare-myfanwy-00-t.txt  # delamare-myfanwy-00-t.txt
wget https://www.gutenberg.ca/ebooks/delamare-penny/delamare-penny-00-t.txt # delamare-penny-00-t.txt

files=(
    "/home/ubuntu/buchanj-midwinter-00-t.txt"
    "/home/ubuntu/carman-farhorizons-00-t.txt"
    "/home/ubuntu/colby-champlain-00-t.txt"
    "/home/ubuntu/cheyneyp-darkbahama-00-t.txt"
    "/home/ubuntu/delamare-bumps-00-t.txt"
    "/home/ubuntu/charlesworth-scene-00-t.txt"
    "/home/ubuntu/delamare-lucy-00-t.txt"
    "/home/ubuntu/delamare-myfanwy-00-t.txt"
    "/home/ubuntu/delamare-penny-00-t.txt"
)

hadoop_times_file="output_hadoop_times.txt"
hadoop_output_dir="/home/ubuntu/output"
hadoop_cmd="/usr/local/hadoop/bin/hadoop jar /usr/local/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-3.4.0.jar wordcount"

spark_times_file="output_spark_times.txt"
spark_cmd="spark-submit /usr/local/spark/examples/src/main/python/wordcount.py"

touch "$hadoop_times_file"

for file in "${files[@]}"; do
    for run in {1..3}; do
        if [ -d "$hadoop_output_dir" ]; then
            rm -r "$hadoop_output_dir"
        fi
        { time $hadoop_cmd "$file" "$hadoop_output_dir" > /dev/null; } 2>> "$hadoop_times_file"
        { time $spark_cmd "$file" > /dev/null; } 2>> "$spark_times_file"
    done
done
'''
