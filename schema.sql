
drop database photosharesolution;
create database photosharesolution;
use photosharesolution;

create table users (
	uid				int	not null	auto_increment,
	gender			varchar(6),
	email			varchar(40)	unique,
	password		varchar(40) not null,
	dob				date,
	hometown		varchar(40),
	fname			varchar(40),
	lname			varchar(40),
	photo_count		int default 0,
	comment_count	int default 0,
	primary key (uid)
);

create table friends (
	from_user_id	int	not null,
	to_user_id		int not null,
	primary key (from_user_id, to_user_id),
	foreign key (from_user_id) references users(uid) on delete cascade,
	foreign key (to_user_id) references users(uid) on delete cascade
);

create table albums (
	album_id		int not null	auto_increment,
	album_name		varchar(40) not null,
	date_created	timestamp not null,
	uid				int not null,
	photo_count		int default 0,
	primary key (album_id),
	foreign key (uid) references users(uid) on delete cascade
);

create table photos (
	photo_id		int not null	auto_increment,
	album_id		int not null,
	caption			varchar(200),
	photo_path		varchar(200) not null,
	primary key (photo_id),
	foreign key (album_id) references albums(album_id) on delete cascade
);

create table comments (
	comment_id		int not null	auto_increment,
	comment_text	varchar(200) not null,
	comment_date	timestamp not null,
	uid				int not null,
	photo_id		int not null,
	primary key (comment_id),
	foreign key (uid) references users(uid) on delete cascade,
	foreign key (photo_id) references photos(photo_id) on delete cascade
);

create table likes (
	uid				int not null,
	photo_id		int not null,
	liked_at		timestamp not null,
	primary key (uid, photo_id),
	foreign key (uid) references users(uid) on delete cascade,
	foreign key (photo_id) references photos(photo_id) on delete cascade
);

create table tags (
	tag_id			int not null	auto_increment,
	tag_name		varchar(40)	not null unique,
	photo_count		int default 0,
	primary key (tag_id)
);

create table photo_tags (
	photo_id		int not null,
	tag_id			int not null,
	primary key (photo_id, tag_id),
	foreign key (photo_id) references photos(photo_id) on delete cascade,
	foreign key (tag_id) references tags(tag_id) on delete cascade
);
