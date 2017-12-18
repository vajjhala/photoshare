import os
import time

import flask
import flask_login
from flask import Flask, render_template, request
from flaskext.mysql import MySQL
from pymysql.cursors import DictCursor

# All the initializations

# Application photoshare initialization
app = Flask(__name__)

# Session initialization
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'SUPER__DUPER__SECRET__KEY'

# Database initialization - cursor configured to return rows in form of
# dictionary

# app.config['MYSQL_DATABASE_USER'] = 'root'
# app.config['MYSQL_DATABASE_PASSWORD'] = 'password'
app.config['MYSQL_DATABASE_DB'] = 'photosharesolution'
app.config['MYSQL_DATABASE_HOST'] = '127.0.0.1'
mysql = MySQL(cursorclass=DictCursor)
mysql.init_app(app)
conn = mysql.connect()

cwd = os.getcwd()
app.config['UPLOAD_FOLDER'] = os.path.join(cwd, "./photos/")
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.mkdir(app.config['UPLOAD_FOLDER'])
print("Upload directory for photos:", app.config['UPLOAD_FOLDER'])

# Login Manager
login_manager = flask_login.LoginManager()
login_manager.init_app(app)


def run_insert_query(query):
    print("Running query: ", query)
    conn.cursor().execute(query)
    conn.commit()


def query_single_row(query):
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    if len(data) == 0:
        return None
    print("Row: ", data)
    return data[0]


def query_all_rows(query):
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    print("Rows: ", data)
    return data


def user_email_exists(email):
    query = "select uid from users where email = '{0}'".format(email)
    print("Checking query: ", query)
    if conn.cursor().execute(query):
        return True
    else:
        return False


def album_exists_for_user(uid, album_name):
    query = '''select * from albums
			 where uid = {0} and album_name = '{1}'
			'''.format(uid, album_name)
    if query_single_row(query) == None:
        return False
    return True


def get_all_albums_for_user(uid):
    query = '''select album_id, users.uid as owner_id, album_name, albums.photo_count, fname
				from albums, users
				where albums.uid = users.uid
				and users.uid = {0}
				order by albums.photo_count desc'''.format(uid)

    return query_all_rows(query)


def get_all_tags_for_user(uid):
    query = '''select distinct tags.tag_id, tags.tag_name, count(*) as photo_count
				 from tags, photos, photo_tags, albums
				 where photo_tags.tag_id = tags.tag_id
				 and photo_tags.photo_id = photos.photo_id
				 and photos.album_id = albums.album_id
				 and albums.uid = {0}
				 group by tags.tag_id'''.format(uid)
    return query_all_rows(query)


def delete_album(user, album_id):
    uid = user.user_info['uid']
    cursor = conn.cursor()
    query = '''delete from albums
			 where uid = {0} and album_id = {1}
			'''.format(uid, album_id)
    cursor.execute(query)

    # Delete photos from the album too
    query = "delete from photos where album_id = {0}".format(album_id)
    cursor.execute(query)
    conn.commit()


def check_if_tag_exists(tag):
    query = "select tag_id from tags where tag_name = '{0}'".format(tag)
    tag_row = query_single_row(query)
    if tag_row == None:
        return None
    return tag_row['tag_id']


def create_new_tag(tag):
    query = "insert into tags (tag_name) values ('{0}')".format(tag)
    run_insert_query(query)
    return check_if_tag_exists(tag)


def handle_photo_tags(tags):
    tag_ids = []
    for tag in tags:
        tag_id = check_if_tag_exists(tag)
        if tag_id == None:
            tag_id = create_new_tag(tag)
        tag_ids.append(tag_id)
    return tag_ids


def get_all_photos_by_tag_for_user(tag_id, page_id, user_id):
    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage
    query = '''select distinct photo_id
			from photo_tags where tag_id = '{0}'
			limit {1} offset {2}'''.format(tag_id, perpage, offset)
    rows = query_all_rows(query)
    if len(rows) == 0:
        return [], "0", "0"

    photo_ids = []
    for row in rows:
        photo_ids.append(row['photo_id'])

    photo_id_list = ",".join(str(photo_id) for photo_id in photo_ids)
    query = '''select caption, photo_id
				from photos, albums
				 where photos.album_id = albums.album_id
				   and albums.uid = {1}
				   and photo_id in ({0})'''.format(photo_id_list, user_id)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    photos = add_show_delete_info_to_photos(photos, user_id)
    photos = add_likes_info_to_photos(photos, user_id)
    photos = add_comments_info_to_photos(photos, user_id)

    return photos, show_next, show_prev


def get_all_photos_by_tag_for_all(tag_id, page_id, user_id):
    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage
    query = '''select distinct photo_id
			from photo_tags where tag_id = '{0}'
			limit {1} offset {2}'''.format(tag_id, perpage, offset)
    rows = query_all_rows(query)
    if len(rows) == 0:
        return [], "0", "0"

    photo_ids = []
    for row in rows:
        photo_ids.append(row['photo_id'])

    photo_id_list = ",".join(str(photo_id) for photo_id in photo_ids)
    query = '''select caption, photo_id
				from photos
				 where photo_id in ({0})'''.format(photo_id_list)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    photos = add_show_delete_info_to_photos(photos, user_id)
    photos = add_likes_info_to_photos(photos, user_id)
    photos = add_comments_info_to_photos(photos, user_id)

    return photos, show_next, show_prev


def search_photos_for_tags(user_id, tags_to_search, page_id):
    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage
    tag_list = tags_to_search.split()
    query_tag_list = []
    num_tags = len(tag_list)
    for tag in tag_list:
        query_tag_list.append("'" + tag + "'")
    tag_list_string = ",".join(query_tag_list)
    query = '''select photo_tags.photo_id as photo_id
				from photo_tags join tags on photo_tags.tag_id = tags.tag_id
				where tags.tag_name in ({0})
				group by photo_tags.photo_id
				having count(distinct tags.tag_id) = {1}
				limit {2} offset {3}'''.format(tag_list_string, num_tags, perpage, offset)
    rows = query_all_rows(query)
    if len(rows) == 0:
        return [], "0", "0"

    photo_ids = []
    for row in rows:
        photo_ids.append(row['photo_id'])

    photo_id_list = ",".join(str(photo_id) for photo_id in photo_ids)
    query = '''select caption, photo_id
				from photos
				 where photo_id in ({0})'''.format(photo_id_list)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    photos = add_show_delete_info_to_photos(photos, user_id)
    photos = add_likes_info_to_photos(photos, user_id)
    photos = add_comments_info_to_photos(photos, user_id)

    return photos, show_next, show_prev


def get_owner_of_the_photo(photo_id):
    query = '''select uid from albums, photos
				where photos.album_id = albums.album_id
				  and photo_id = {0}'''.format(photo_id)
    row = query_single_row(query)
    if row == None:
        return 0
    return row['uid']


def add_show_delete_info_to_photos(photos, user_id):
    for photo in photos:
        owner_id = get_owner_of_the_photo(photo['photo_id'])
        if int(owner_id) == int(user_id):
            photo['show_delete'] = "1"
        else:
            photo['show_delete'] = "0"
        photo['owner_id'] = owner_id

    return photos


def get_all_photos_in_album(album_id, page_id, user_id):
    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage
    query = '''select caption, photo_id
			from photos where album_id = '{0}'
			limit {1} offset {2}'''.format(album_id, perpage, offset)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    photos = add_show_delete_info_to_photos(photos, user_id)
    photos = add_likes_info_to_photos(photos, user_id)
    photos = add_comments_info_to_photos(photos, user_id)

    return photos, show_next, show_prev


def get_all_photos_of_user(page_id, owner_id, user_id):
    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage
    query = '''select caption, photo_id
			from photos, albums
			 where albums.album_id = photos.album_id
			and albums.uid = {0}
			limit {1} offset {2}'''.format(owner_id, perpage, offset)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    photos = add_show_delete_info_to_photos(photos, user_id)
    photos = add_likes_info_to_photos(photos, user_id)
    photos = add_comments_info_to_photos(photos, user_id)

    return photos, show_next, show_prev


def get_all_comments_by_user(page_id, owner_id, user_id):
    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage
    query = '''select caption, photos.photo_id as photo_id, comment_text, comment_date, fname 
			from photos, comments, users
			 where comments.photo_id = photos.photo_id
				and comments.uid = users.uid
			and comments.uid = {0}
			limit {1} offset {2}'''.format(owner_id, perpage, offset)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    photos = add_show_delete_info_to_photos(photos, user_id)
    photos = add_likes_info_to_photos(photos, user_id)
    photos = add_comments_info_to_photos(photos, user_id)

    return photos, show_next, show_prev


def add_likes_info_to_photos(photos, user_id):
    for photo in photos:
        photo_id = photo['photo_id']
        query = '''select count(uid) as like_count
					from likes
					where photo_id  = {0}
					group by photo_id'''.format(photo_id)
        row = query_single_row(query)
        if row == None:
            photo['num_likes'] = "0"
        else:
            photo['num_likes'] = row['like_count']

        # User is owner
        if int(photo['owner_id']) == int(user_id) or int(user_id) == -1:
            photo['show_like'] = "0"
        else:
            photo['show_like'] = "1"
    return photos


def add_comments_info_to_photos(photos, user_id):
    for photo in photos:
        photo_id = photo['photo_id']
        query = '''select count(uid) as comment_count
					from comments
					where photo_id  = {0}
					group by photo_id'''.format(photo_id)
        row = query_single_row(query)
        if row == None:
            photo['num_comments'] = "0"
        else:
            photo['num_comments'] = row['comment_count']

        if int(photo['owner_id']) == int(user_id):
            photo['show_comment_text'] = "0"
        else:
            photo['show_comment_text'] = "1"
    return photos


def get_users_who_liked_photo(photo_id):
    query = '''select fname
				from users
				where uid in ( select uid
								from likes
								where photo_id = {0} )'''.format(photo_id)
    rows = query_all_rows(query)
    users = []
    for row in rows:
        users.append(row['fname'])
    return users


def get_user_comments_on_photo(photo_id):
    query = '''select comment_text, comment_date, fname
				from users, comments
				where comments.photo_id = {0}
				  and users.uid = comments.uid'''.format(photo_id)
    return query_all_rows(query)


def get_commenting_uid(uid):
    if int(uid) != -1:
        return uid

    # Get the guest user_id
    query = '''select uid from users
				 where fname = "guest"
				 and lname = "guest"'''
    row = query_single_row(query)
    if row == None:
        raise Exception("Create guest user")

    return row['uid']


def get_album_name(album_id):
    query = "select album_name from albums where album_id = '{0}'".format(album_id)
    return query_single_row(query)['album_name']


def get_album_id_for_photo(photo_id):
    query = '''select album_id from photos where photo_id = {0}'''.format(photo_id)
    print("Query:", query)
    return query_single_row(query)['album_id']


def add_user(user_info):
    query = '''
				insert into users (fname, lname, dob, email, password, hometown,
									 gender) values ('{0}', '{1}', '{2}', '{3}',
									 '{4}', '{5}', '{6}')
			'''.format(user_info.get('firstname'), user_info.get('lastname'),
                       user_info.get('dob'), user_info.get('email'),
                       user_info.get('password'), user_info.get('hometown'),
                       user_info.get('gender'))
    run_insert_query(query)


def get_uname_uid(user):
    if user.is_anonymous():
        username = 'guest'
        user_id = -1
    else:
        username, user_id = user.get_name_id()
    return username, user_id


def get_all_friends_for_user(uid):
    query = '''select DISTINCT users.uid, users.fname, users.lname 
               from friends, users
               where friends.from_user_id = '{0}' and 
                     users.uid = friends.to_user_id
               '''.format(uid)
    return query_all_rows(query)


@login_manager.user_loader
def user_loader(uid):
    if not (uid):
        return None

    query = "select * from users where uid = {0}".format(int(uid))
    user_row = query_single_row(query)
    if user_row == None:
        return None

    photoshare_user = PhotoShareUser(user_row)
    return photoshare_user


# Default route - This is the first page
@app.route('/', methods=['GET'])
def load_photoshare_login():
    return render_template('start.html')


@app.route('/login', methods=['POST'])
def login_user():
    email = request.form.get('email')
    password = request.form.get('password')
    query = "select * from users where email = '{0}'".format(email)
    user_row = query_single_row(query)
    if user_row == None:
        return render_template('error.html', message='User Does not exist')

    if user_row['password'] != password:
        return render_template('error.html', message='Invalid password')

    photoshare_user = PhotoShareUser(user_row)
    flask_login.login_user(photoshare_user)
    # return render_template('browse.html',
    #	 username = photoshare_user.user_info['fname'])
    return flask.redirect(flask.url_for('browse', uid=user_row['uid']))


@app.route('/Home')
@flask_login.login_required
def show_user_homepage():
    user_name = flask_login.current_user.user_info['fname']
    return render_template('profile.html', name=user_name)


# Let us register new users to our app
@app.route('/register', methods=['GET'])
def show_registration_form():
    return render_template('register.html')


@app.route('/register', methods=['POST'])
def register_new_user():
    email = request.form.get('email')
    if user_email_exists(email):
        print('User with email ', email, ' already exists ')
        return render_template('error.html', message='User already exists')

    # Unique email, lets register the user
    add_user(request.form)
    return render_template('start.html')


@app.route('/create_album', methods=['GET'])
def show_create_album():
    uid = request.args.get('uid')
    return render_template('create_album.html',
                           message="Lets start with new album", uid=uid)


@app.route('/create_album', methods=['POST'])
def create_new_album():
    uid = request.form.get('uid')
    if request.form.get('submit') == "Cancel":
        return render_template('browse.html', uid=uid)

    album_name = request.form.get('album_name')
    if album_exists_for_user(uid, album_name):
        return render_template('create_album.html', uid=uid,
                               message="Album with name '{0}' already exists".format(album_name))

    date_of_creation = time.strftime("%Y-%m-%d")
    query = '''insert into albums (album_name, date_created, uid) values
				('{0}', '{1}', {2})'''.format(album_name, date_of_creation,
                                              uid)
    run_insert_query(query)
    return render_template('browse.html',
                           message="Album with name '{0}' created".format(album_name),
                           uid=uid)


@app.route('/my_albums')
def show_user_albums():
    uid = request.args.get('uid')
    user = user_loader(uid)
    albums = get_all_albums_for_user(uid)
    if len(albums) == 0:
        return render_template('show_albums.html', user_id=uid,
                               message="No albums for user '{0}'".format(user.user_info['fname']))

    return render_template('show_albums.html', username=user.user_info['fname'],
                           user_id=user.user_info['uid'], albums=albums,
                           source='show_user_albums')


@app.route('/my_tags')
def show_user_tags():
    uid = request.args.get('uid')
    user = user_loader(uid)
    tags = get_all_tags_for_user(uid)
    if len(tags) == 0:
        return render_template('show_tags.html', user_id=uid,
                               message="No tags for user '{0}'".format(user.user_info['fname']))

    return render_template('show_tags.html', username=user.user_info['fname'],
                           user_id=user.user_info['uid'], tags=tags,
                           source='show_user_tags')


@app.route('/show_photos_of_album', methods=['GET', 'POST'])
def show_photos_of_album():
    album_id = request.args.get('album_id')
    owner_id = request.args.get('owner_id')
    user_id = request.args.get('user_id')
    source = request.args.get('source')
    page_id = int(request.args.get('page_id'))
    photos, show_next, show_prev = get_all_photos_in_album(album_id, page_id,
                                                           user_id)
    album_name = get_album_name(album_id)
    params = {}
    params['user_id'] = user_id
    params['album_id'] = album_id
    params['album_name'] = album_name
    params['page_id'] = page_id
    params['source'] = source
    params['source_photos'] = 'show_photos_of_album'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next

    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/show_photos_of_tag', methods=['GET', 'POST'])
def show_photos_of_tag():
    tag_id = request.args.get('tag_id')
    tag_name = request.args.get('tag_name')
    user_id = request.args.get('user_id')
    source = request.args.get('source')
    page_id = int(request.args.get('page_id'))
    if source == 'show_user_tags':
        photos, show_next, show_prev = get_all_photos_by_tag_for_user(tag_id, page_id, user_id)
    else:
        photos, show_next, show_prev = get_all_photos_by_tag_for_all(tag_id, page_id, user_id)

    params = {}
    params['user_id'] = user_id
    params['tag_id'] = tag_id
    params['tag_name'] = tag_name
    params['page_id'] = page_id
    params['source'] = source
    params['source_photos'] = 'show_photos_of_tag'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next
    params['message'] = "Photos with tag '{0}'".format(tag_name)
    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/photos/<int:photo_id>')
def return_photo(photo_id):
    query = "select photo_path from photos where photo_id = {0}".format(photo_id)
    row = query_single_row(query)
    if row == None:
        return ""

    return flask.send_file(row['photo_path'])


@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    photo_id = request.form.get('photo_id')
    params = eval(request.form.get('params'))
    if 'album_id' not in params:
        album_id = get_album_id_for_photo(photo_id)
    else:
        album_id = params['album_id']

    cursor = conn.cursor()
    query = '''select distinct tag_id from photo_tags
			 where photo_id = {0}'''.format(photo_id)
    tag_rows = query_all_rows(query)
    query = "delete from photos where photo_id = {0}".format(photo_id)
    cursor.execute(query)
    query = "delete from photo_tags where photo_id = {0}".format(photo_id)
    cursor.execute(query)

    for row in tag_rows:
        query = '''update tags set photo_count = photo_count - 1
				where tag_id = {0}'''.format(row['tag_id'])
        cursor.execute(query)

    query = '''update users set photo_count = photo_count - 1
			where uid = {0}'''.format(params['user_id'])
    cursor.execute(query)
    query = '''update albums set photo_count = photo_count - 1
			where album_id = {0}'''.format(album_id)
    cursor.execute(query)
    conn.commit()

    page_id = int(params['page_id'])
    if params['source_photos'] == 'show_photos_of_album':
        photos, show_next, show_prev = get_all_photos_in_album(params['album_id'],
                                                               page_id, params['user_id'])
    elif params['source_photos'] == 'show_photos_of_tag':
        tag_id = params['tag_id']
        photos, show_next, show_prev = get_all_photos_by_tag_for_user(tag_id, page_id,
                                                                      params['user_id'])
    elif params['source_photos'] == 'show_photos_of_user':
        owner_id = params['owner_id']
        photos, show_next, show_prev = get_all_photos_of_user(page_id,
                                                              owner_id, params['user_id'])
    elif params['source_photos'] == 'show_comments_by_user':
        owner_id = params['owner_id']
        photos, show_next, show_prev = get_all_comments_by_user(page_id,
                                                                owner_id, params['user_id'])
    else:
        raise Exception("Unahndled source photos")

    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next
    params['message'] = "Deleted photo successfully"
    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/like_photo', methods=['POST'])
def like_photo():
    photo_id = request.form.get('photo_id')
    params = eval(request.form.get('params'))
    uid = params['user_id']
    liked_at = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()

    # We don't want same user to like same photo more than once
    # Hence, insert ignore
    query = '''insert ignore into likes (uid, photo_id, liked_at) values
				({0}, {1}, '{2}')'''.format(uid, photo_id, liked_at)
    cursor.execute(query)
    conn.commit()
    photos = eval(request.form.get('photos'))
    photos = add_likes_info_to_photos(photos, uid)
    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/comment_on_photo', methods=['POST'])
def comment_on_photo():
    photo_id = request.form.get('photo_id')
    params = eval(request.form.get('params'))
    comment_text = request.form.get('comment')
    uid = params['user_id']
    commented_at = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()

    commenting_uid = get_commenting_uid(uid)
    # We don't want same user to like same photo more than once
    # Hence, insert ignore
    query = '''insert into comments (uid, photo_id, comment_text, comment_date)
			   values ({0}, {1}, '{2}', '{3}')'''.format(commenting_uid, photo_id,
                                                       comment_text, commented_at)
    cursor.execute(query)
    if int(uid) != -1:
        query = '''update users set comment_count = comment_count + 1
			       where uid = {0}'''.format(uid)
        cursor.execute(query)
    conn.commit()
    photos = eval(request.form.get('photos'))
    photos = add_comments_info_to_photos(photos, uid)
    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/show_photo_details')
def show_photo_details():
    photo = eval(request.args.get('photo'))
    photos = eval(request.args.get('photos'))
    params = eval(request.args.get('params'))
    photo_id = photo['photo_id']
    users_who_liked = get_users_who_liked_photo(photo_id)
    comments = get_user_comments_on_photo(photo_id)
    return render_template('show_photo_details.html', photo=photo,
                           liked_users=users_who_liked, comments=comments,
                           photos=photos, params=params)


@app.route('/upload_photo', methods=['GET'])
@flask_login.login_required
def show_upload_photo_page():
    uid = request.args.get('uid')
    user = user_loader(uid)
    albums = get_all_albums_for_user(uid)
    if len(albums) == 0:
        return render_template('error.html',
                               message='''You need to create at least one album first
						to upload photo''', home=True)

    return render_template('upload_photo.html', uid=uid, albums=albums)


@app.route('/upload_photo', methods=['POST'])
def upload_the_photo():
    uid = request.form.get('uid')
    user = user_loader(uid)
    photo_location = request.files['photo_location']
    photo_caption = request.form.get('photo_caption')
    photo_tags = request.form.get('tags').split(' ')
    album_id = request.form.get('album_id')

    file_name = photo_location.filename
    photo_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
    photo_location.save(photo_path)
    # Lets create all the required tags first
    photo_tag_ids = handle_photo_tags(photo_tags)
    print("Got Tag ids: ", photo_tag_ids)
    cursor = conn.cursor()
    insert_query = '''insert into photos (album_id, caption, photo_path) values
					(%s, %s, %s)'''
    args = (album_id, photo_caption, photo_path)
    cursor.execute(insert_query, args)
    photo_id = cursor.lastrowid
    for tag_id in photo_tag_ids:
        query = '''insert into photo_tags (photo_id, tag_id) values
				({0}, {1})'''.format(photo_id, tag_id)
        cursor.execute(query)
        query = '''update tags set photo_count = photo_count + 1
				where tag_id = {0}'''.format(tag_id)
        cursor.execute(query)
    query = '''update users set photo_count = photo_count + 1
			where uid = {0}'''.format(user.user_info['uid'])
    cursor.execute(query)
    query = '''update albums set photo_count = photo_count + 1
			where album_id = {0}'''.format(album_id)
    cursor.execute(query)
    conn.commit()
    return render_template('browse.html',
                           message="Photo Uploaded", uid=uid)


@app.route('/delete_album', methods=['POST'])
def delete_user_album():
    album_id = request.form.get('album_id')
    user_id = request.form.get('user_id')
    user = user_loader(user_id)
    delete_album(user, album_id)
    return flask.redirect(flask.url_for('show_user_albums', uid=user_id))


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return render_template('start.html')


@app.route('/browse')
def browse():
    return render_template('browse.html', uid=request.args.get('uid'),
                           message="!! Welcome to Photo Share !!")


@app.route('/browse_show_albums')
def browse_show_albums():
    uid = int(request.args.get('uid'))
    if uid == -1:
        username = 'guest'
    else:
        user = user_loader(uid)
        username = user.user_info['fname']
    query = '''select album_id, users.uid as owner_id, album_name, albums.photo_count, fname
				from albums, users
				where albums.uid = users.uid
				order by albums.photo_count desc'''
    albums = query_all_rows(query)
    return render_template('show_albums.html',
                           username=username, user_id=uid, albums=albums,
                           source="browse_show_albums")


@app.route('/browse_show_photos')
def browse_show_photos():
    uid = int(request.args.get('uid'))
    page_id = int(request.args.get('page_id'))
    perpage = 5

    params = {}
    params['user_id'] = uid
    params['page_id'] = page_id
    params['source'] = 'browse'
    params['source_photos'] = 'browse_show_photos'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = "1"
    params['show_next'] = "1"
    params['show_like'] = "1"
    if int(uid) == -1:
        params['show_like'] = "0"

    offset = (page_id - 1) * perpage
    query = '''select caption, photo_id
				from photos
				limit {0} offset {1}'''.format(perpage, offset)
    photos = query_all_rows(query)
    if len(photos) < perpage:
        params['show_next'] = "0"
    if page_id == 1:
        params['show_prev'] = "0"

    photos = add_show_delete_info_to_photos(photos, uid)
    photos = add_likes_info_to_photos(photos, uid)
    photos = add_comments_info_to_photos(photos, uid)
    return render_template('show_photos.html', photos=photos,
                           params=params)


@app.route('/browse_show_tags')
def browse_show_tags():
    uid = int(request.args.get('uid'))
    if uid == -1:
        username = 'guest'
    else:
        user = user_loader(uid)
        username = user.user_info['fname']
    query = '''select tag_id, tag_name, photo_count
				from tags
				where photo_count > 0
				order by photo_count desc'''
    tags = query_all_rows(query)
    return render_template('show_tags.html',
                           user_id=uid, tags=tags,
                           source="browse_show_tags")


@app.route('/browse_search_photos', methods=['GET'])
def show_search_photos():
    uid = request.args.get('uid')
    return render_template('search_photos.html', uid=uid, params={})


@app.route('/browse_search_photos', methods=['POST'])
def browse_search_photos():
    uid = request.form.get('uid')
    if int(uid) == -1:
        username = 'guest'
    else:
        user = user_loader(uid)
        username = user.user_info['fname']

    if request.form.get('submit') == "Cancel":
        return render_template('browse.html', uid=uid)

    params = eval(request.form.get('params'))
    tags_to_search = request.form.get('tags_to_search')
    page_id = int(request.form.get('page_id'))
    photos, show_next, show_prev = search_photos_for_tags(uid, tags_to_search, page_id)
    if len(photos) == 0:
        params['message'] = "Couldn't find any photos for '{0}'".format(tags_to_search)
        return render_template('search_photos.html', uid=uid, params=params)
    params['user_id'] = uid
    params['tag_names'] = tags_to_search
    params['page_id'] = page_id
    params['source'] = 'show_search_photos'
    params['source_photos'] = 'browse_search_photos'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next
    params['message'] = "Photos with tags '{0}'".format(tags_to_search)
    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/top_users')
def show_top_users():
    uid = request.args.get('uid')
    if int(uid) == -1:
        username = 'guest'
    else:
        user = user_loader(uid)
        username = user.user_info['fname']

    query = '''select fname, uid, photo_count, comment_count,
				(photo_count + comment_count) as total_activity
				from users
				where fname != 'guest'
				and lname != 'guest'
				order by total_activity desc
				limit 10'''
    users = query_all_rows(query)
    return render_template('top_users.html', users=users, uid=uid)


@app.route('/show_photos_of_user')
def show_photos_of_user():
    user_id = request.args.get('uid')
    source = request.args.get('source')
    page_id = int(request.args.get('page_id'))
    owner_id = int(request.args.get('owner_id'))
    photos, show_next, show_prev = get_all_photos_of_user(page_id,
                                                          owner_id, user_id)
    params = {}
    params['owner_id'] = owner_id
    params['user_id'] = user_id
    params['page_id'] = page_id
    params['source'] = source
    params['source_photos'] = 'show_photos_of_user'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next

    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/show_comments_by_user')
def show_comments_by_user():
    user_id = request.args.get('uid')
    source = request.args.get('source')
    page_id = int(request.args.get('page_id'))
    owner_id = int(request.args.get('owner_id'))
    photos, show_next, show_prev = get_all_comments_by_user(page_id, owner_id, user_id)
    params = {}
    params['owner_id'] = owner_id
    params['user_id'] = user_id
    params['page_id'] = page_id
    params['source'] = source
    params['source_photos'] = 'show_comments_by_user'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next

    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/browse_search_comments', methods=['GET'])
def show_search_comments():
    uid = request.args.get('uid')
    return render_template('search_comments.html', uid=uid, params={})


def search_users_for_comments(user_id, comments_to_search, page_id):
    comments_text = "'" + comments_to_search + "'"
    query = '''select users.fname, comments.uid, count(*) as comment_count
				 from comments, users
         		where comment_text = {0} and comments.uid = users.uid
	         group by uid order by comment_count desc
      '''.format(comments_text)
    rows = query_all_rows(query)
    return rows


@app.route('/browse_search_comments', methods=['POST'])
def browse_search_comments():
    uid = request.form.get('uid')
    if int(uid) == -1:
        username = 'guest'
    else:
        user = user_loader(uid)
        username = user.user_info['fname']

    if request.form.get('submit') == "Cancel":
        return render_template('browse.html', uid=uid)

    params = eval(request.form.get('params'))
    comments_to_search = request.form.get('comments_to_search')
    page_id = int(request.form.get('page_id'))
    users_found = search_users_for_comments(uid, comments_to_search, page_id)
    if len(users_found) == 0:
        params['message'] = "Couldn't find any users for '{0}'".format(comments_to_search)
        return render_template('search_comments.html', uid=uid, params=params)

    params['user_id'] = uid
    params['comment_names'] = comments_to_search
    params['page_id'] = page_id
    params['source'] = 'show_search_comments'
    params['source_comments'] = 'browse_search_comments'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['message'] = "Users with comments '{0}'".format(comments_to_search)
    return render_template('show_comments.html', params=params,
                           users=users_found)


@app.route('/show_photos_user_may_like')
def show_photos_user_may_like():
    uid = request.args.get('uid')
    page_id = int(request.args.get('page_id'))
    if int(uid) == -1:
        return render_template('browse.html', uid=-1,
                               message="Not available for guests")

    user = user_loader(uid)
    username = user.user_info['fname']

    # Lets first get most popular 5 tags for user
    query = '''select photo_tags.tag_id as tag_id,
					  count(photo_tags.photo_id) as photo_count_for_tag
				 from photos, albums, photo_tags
				where albums.uid = {0}
				  and photos.album_id = albums.album_id
				  and photo_tags.photo_id = photos.photo_id
			 group by photo_tags.tag_id
			 order by photo_count_for_tag desc
				limit 5;'''.format(uid)
    print("Popular tag query:", query)
    most_popular_tags = query_all_rows(query)
    if len(most_popular_tags) == 0:
        return render_template('browse.html', uid=uid,
                               message="Couldn't find popular tag for you")

    popular_tag_ids = []
    for tag in most_popular_tags:
        popular_tag_ids.append(tag['tag_id'])
    tag_id_list = ",".join(str(tag_id) for tag_id in popular_tag_ids)

    # Now lets find the photos with these popular tags, but are not
    # uploaded by the logged in user
    #
    # This is interesting, the final search of the photos should happen
    # in the result set returned by this query.  This is because, the
    # result set includes the photos (not of logged in user) with the
    # tags we are interested in.  So, this query serve as the new
    # table that we want to issue our final query on.  You can imagine
    # this table as miniature version of photo_tags, but only with
    # tags from most popular tags and corresponding photos.
    #
    # But, we also want to get the distinct photo_ids from the result
    # of this query for our final search
    table_query = '''select photo_tags.photo_id as photo_id,
							photo_tags.tag_id as tag_id
				 	   from photo_tags, photos, albums
					  where albums.uid != {0}
					    and albums.album_id = photos.album_id
						and photos.photo_id = photo_tags.photo_id
						and tag_id in ({1})'''.format(uid, tag_id_list)
    print("Table query:", table_query)
    photos_with_tags = query_all_rows(table_query)
    if len(photos_with_tags) == 0:
        return render_template('browse.html', uid=uid,
                               message="Couldn't find photos matching your popular tags")

    # Using set to find distinct photo ids
    distinct_photos = set()
    for photo in photos_with_tags:
        distinct_photos.add(photo['photo_id'])

    photo_id_list = ",".join(str(photo_id) for photo_id in distinct_photos)
    print("Photo id list:", photo_id_list)

    perpage = 5
    show_next = "1"
    show_prev = "1"
    offset = (int(page_id) - 1) * perpage

    # Now the final query to get the results
    final_query = '''select photo_id, count(tag_id) as num_tags
					   from ( {0} ) subset_photo_tags
					  where photo_id in ({1})
				   group by photo_id
				   order by num_tags desc
				   limit {2} offset {3}'''.format(table_query, photo_id_list,
                                                  perpage, offset)
    may_like_photo_set = query_all_rows(final_query)
    if len(may_like_photo_set) == 0:
        return render_template('browse.html', uid=uid,
                               message="No photos for recommendation")
    if len(may_like_photo_set) < perpage:
        show_next = "0"
    if page_id == 1:
        show_prev = "0"

    final_photo_ids = []
    for photo in may_like_photo_set:
        final_photo_ids.append(photo['photo_id'])

    final_photo_id_list = ",".join(str(photo_id) for photo_id in final_photo_ids)

    query = '''select caption, photo_id
				 from photos
				where photo_id in ({0})'''.format(final_photo_id_list)
    photos = query_all_rows(query)
    photos = add_show_delete_info_to_photos(photos, uid)
    photos = add_likes_info_to_photos(photos, uid)
    photos = add_comments_info_to_photos(photos, uid)

    params = {}
    params['user_id'] = uid
    params['page_id'] = page_id
    params['source'] = 'browse'
    params['source_photos'] = 'show_photos_user_may_like'
    params['prev_page'] = page_id - 1
    params['next_page'] = page_id + 1
    params['show_prev'] = show_prev
    params['show_next'] = show_next
    params['message'] = "Photos you may like"
    return render_template('show_photos.html', params=params,
                           photos=photos)


@app.route('/my_friends')
def show_user_friends():
    uid = request.args.get('uid')
    user = user_loader(uid)
    friends = get_all_friends_for_user(uid)
    if len(friends) == 0:
        return render_template('show_friends.html', user_id=uid,
                               message="No friends for user '{0}'".format(user.user_info['fname']))

    return render_template('show_friends.html', username=user.user_info['fname'],
                           user_id=user.user_info['uid'], friends=friends,
                           source='show_user_friends')


@app.route('/add_friends', methods=['GET'])
@flask_login.login_required
def add_friends_page():
    uid = request.args.get('uid')
    friends = list(map(lambda x: x['uid'], list(get_all_friends_for_user(uid))))
    friends_of_friends = list()
    for friend in friends:
        query = '''select email, fname, uid 
                    from friends inner join users 
                    on friends.to_user_id=users.uid 
                    where friends.from_user_id='{0}';'''.format(friend)
        query_results = query_all_rows(query)
        friends_of_friends.extend(query_results)
    print(friends_of_friends)
    recommendations = list(filter(lambda x: x['uid'] not in friends and x['uid'] != uid,
                                  friends_of_friends))
    print(recommendations)
    return render_template('add_friends.html', uid=uid, recommendations=recommendations)


@app.route('/add_friends', methods=['POST'])
def add_friends():
    uid = request.form.get('uid')
    friend_email = request.form.get('friend')
    query = '''select uid, fname from users where email = '{0}' '''.format(friend_email)
    print('Checking query:', query)
    if conn.cursor().execute(query) == False:
        return render_template('add_friends.html', uid=uid, message='No such user')

    cursor = conn.cursor()
    cursor.execute(query)
    friend_ = cursor.fetchall()

    if int(friend_[0]['uid']) == int(request.form.get('uid')):
        return render_template('add_friends.html', uid=uid,
                               message='A user cannot be friends with himself')
    friend_uid = friend_[0]['uid']
    friend_name = friend_[0]['fname']
    all_friends_uids = map(lambda x: x['uid'],
                           list(get_all_friends_for_user(uid)))
    if friend_uid in all_friends_uids:
        return render_template('browse.html',
                               message="{} is already a friend".format(friend_name),
                               uid=uid)
    else:
        cursor = conn.cursor()
        # insert into user
        insert_query = ''' insert into friends (from_user_id, to_user_id) 
                           values ({0}, {1})'''.format(uid, friend_uid)
        print(insert_query)
        cursor.execute(insert_query)
        # insert into friend
        insert_query = ''' insert into friends (from_user_id, to_user_id) 
		                           values ({1}, {0})'''.format(uid, friend_uid)
        print(insert_query)
        cursor.execute(insert_query)
        conn.commit()
        return render_template('browse.html',
                               message="{} is added".format(friend_name), uid=uid)


class PhotoShareUser(flask_login.UserMixin):
    def __init__(self, row, guest=False):
        if guest:
            self.user_info = {}
            self.user_info['fname'] = 'guest'
            self.user_info['uid'] = -1
            self.guest_user = True
            self.id = -1
        else:
            self.id = row['uid']
            self.user_info = row
            self.guest_user = False

    def get_name_id(self):
        return self.user_info['fname'], self.id

    def is_authenticated(self):
        if self.user_info:
            return True
        return False

    def is_active(self):
        return True

    def is_anonymous(self):
        if self.guest_user:
            return True
        return False

    def get_id(self):
        return str(self.id).encode('utf-8')


if __name__ == '__main__':
    app.run(port=5231, debug=True)
