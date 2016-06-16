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
const cluster = require('cluster')
const CPUs = require('os').cpus().length

if (cluster.isMaster) {
  for (var i = CPUs; i > 0; i--) {
    cluster.fork()
  }
  cluster.on('exit', (worker, node, signal) => {
    console.log(`worker ${worker.process.pid} died`);
    console.log(`node: ${node}`);
    console.log(`signal: ${signal}`);
    cluster.fork()
  })
} else {
  app.listen(port, () => {
    console.log(`listening on ${port}`)
  })
}
