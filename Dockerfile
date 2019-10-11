# Cap docker demo
FROM xenocider/container:python3.7.3
LABEL maintainer="xenos <xenos.lu@gmail.com>"

COPY . /cap

RUN pip3 install -r /cap/requirements.txt -i http://pypi.douban.com/simple --trusted-host pypi.douban.com &&\
    rm -rf /root/.cache

ENV GITHUB_CLIENT_ID ""
ENV GITHUB_CLIENT_SECRET ""
VOLUME /cap/config
EXPOSE 8888
WORKDIR /cap
CMD ["/usr/bin/python3", "/cap/cap.py"]
