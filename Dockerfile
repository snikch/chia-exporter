FROM chia

RUN python3.8 -m pip install prometheus_client configargparse httplib2

COPY chia-exporter.py /usr/local/sbin/chia-exporter

ENTRYPOINT ["/usr/local/sbin/chia-exporter"]
