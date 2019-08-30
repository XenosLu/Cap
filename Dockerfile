# Cap docker demo
FROM xenocider/container:python3.7.3
LABEL maintainer="xenos <xenos.lu@gmail.com>"

COPY . /cap

RUN pip3 install -r /cap/requirements.txt &&\
    rm -rf /root/.cache

ENV GITHUB_CLIENT_ID ""
ENV GITHUB_CLIENT_SECRET ""
VOLUME /cap/config
EXPOSE 8888
CMD ["/usr/bin/python3", "/cap/cap.py"]
