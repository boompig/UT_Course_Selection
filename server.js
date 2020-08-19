/*
NOTE: this was not my original implementation
My original implementation was using PHP
However I find it easier to write in node now and I want to make this repo usable
*/

// imports
const express = require('express');
const morgan = require('morgan');
const knex = require('knex')({
    client: 'sqlite3',
    connection: {
        filename: './courses.db',
    },
});
const bookshelf = require('bookshelf')(knex);

const app = express();

const Course = bookshelf.model('Course', {
    tableName: 'courses',
});

const Offering = bookshelf.model('Offering', {
    tableName: 'timetable',
});

// globals
const PORT = 5050;

// app config
app.use(morgan('dev'));
app.use('/', express.static('public'));

// routes
app.get('/api/offerings', async (req, res) => {
    const offerings = await Offering.fetchAll();
    res.json(offerings);
});

app.get('/api/courses', async (req, res) => {
    const courses = await Course.fetchAll();
    res.json(courses);
});

// start the server
app.listen(PORT, () => {
    // eslint-disable-next-line
    console.log(`Running on http://localhost:${PORT}`);
});
