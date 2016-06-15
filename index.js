#!/usr/bin/node

'use strict'

require('babel-core/register')({
  'presets': [
    'es2015',
    'stage-0'
  ]
});
require('babel-polyfill');
const app = require('./app.js');
const port = process.env.PORT || 8080
app.listen(port, () => {
  console.log(`listening on ${port}`)
})
