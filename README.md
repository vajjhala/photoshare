

```python
1) Start MySQL:
   On my computer the command would be:

      mysql -u root -p 
      
   The username will be different on other systems.
    
2) create and add the database schema:
  
  mysql> source ~/..path to schema.sql../schema.sql

3) Edit photoshare.py file.

    Uncomment lines 22 and 23. And change the mysql username and passwaord
    to match your systems username and password.
    
    Example:
        app.config['MYSQL_DATABASE_USER'] = 'root'
        app.config['MYSQL_DATABASE_PASSWORD'] = 'mysqlpassword'
  
4) Run the server.
     
     python3 photoshare.py 
    
   Your output should look like:
    
   Upload directory for photos: /.. path to photos../photos/
 * Running on http://127.0.0.1:5231/ (Press CTRL+C to quit)
 * Restarting with stat
Upload directory for photos: /..path to photos ../photos/
 * Debugger is active!
 * Debugger PIN: 302-094-934
127.0.0.1 - - [18/Dec/2017 15:06:26] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [18/Dec/2017 15:06:29] "GET /register HTTP/1.1" 200 -

 
5) Open your browser to the specified url, http://127.0.0.1:5231/, in this case.
    
Now you are all set to start sharing photos with friends and family !

Notes:
    The password storage system is insecure, so be vary of that. 


```
