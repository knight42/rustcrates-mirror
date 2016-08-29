README
============

nginx should suffice for setting up reverse proxy for crates.io:

```
server {
    listen 80;
    listen 443 ssl http2;
    listen [::]:80;
    listen [::]:443 ssl http2;

    server_name crates-io.example.com

    access_log  /var/log/nginx/crates_access.log;
    error_log   /var/log/nginx/crates_error.log;

    ssl_certificate  /etc/nginx/key/example.com.crt;
    ssl_certificate_key /etc/nginx/key/example.com.key;

    proxy_buffering on;
    proxy_ssl_server_name on;
    proxy_read_timeout 90s;

    proxy_cache STATIC;
    proxy_cache_valid 200 12h;
    proxy_cache_valid 400 504 1m;
    proxy_cache_valid any 5m;
    proxy_cache_revalidate on;
    proxy_cache_use_stale error timeout invalid_header updating http_500 http_502 http_503 http_504;

    location / {
        proxy_pass https://crates.io;
        proxy_redirect https://crates-io.s3-us-west-1.amazonaws.com/ /;
        error_page 504 =302 https://crates.io$request_uri;

    }

    location /crates/ {
        proxy_pass https://crates-io.s3-us-west-1.amazonaws.com;
        error_page 504 =302 https://crates-io.s3-us-west-1.amazonaws.com$request_uri;
    }
}
```
