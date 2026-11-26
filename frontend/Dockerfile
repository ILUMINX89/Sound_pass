# Imagen del frontend: nginx sirviendo los archivos estáticos
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html style.css script.js admin.html admin.css admin.js /srv/soundpass/
EXPOSE 80
