#!/usr/bin/node

'use strict'

//const request = require('request');

const fs = require('fs');
//const util = require('util');
//const http = require('http');
//const https = require('https');
//const EventEmitter = require('events');
//const child = require('child_process');
//const exec = require('child_process').exec;
//const spawn = require('child_process').spawn;
const Koa = require('koa');
const app = new Koa();
const router = require('koa-router')();

router.get('/api/v1/crates/:name/:version/download', async (ctx) => {
  //ctx.body = await
})

app.on('error', function(err, ctx) {
  console.log(err)
  logger.error('server error', err, ctx);
});

const port = 8080
app.listen(port)
