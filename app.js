#!/usr/bin/node

'use strict'

const fs = require('fs');
const process = require('process');
const path = require('path');
const https = require('https');

const Koa = require('koa');
const app = new Koa();
const router = require('koa-router')();
const Promise = require('bluebird');

const CratesDir = process.env.CRATES_DIR || '/tmp/crates'

async function isExist(path) {
  return new Promise((ful, rej) => {
    fs.stat(path, (err) => {
      ful(!err)
    })
  })
}

function mkdir(dir) {
  return new Promise((ful, rej) => {
    fs.mkdir(dir, () => {
      ful()
    })
  })
}

async function promiseGet(url) {
  return new Promise((ful, rej) => {
    https.get(url, (res) => {
      ful(res)
    })
  })
}

async function getTar(name, version) {
  const localFile = path.join(CratesDir, name, `${name}@${version}`)
  if (await isExist(localFile)) {
    return Promise.resolve(fs.createReadStream(localFile))
  }

  const url = `https://crates.io/api/v1/crates/${name}/${version}/download`
  const res = await promiseGet(url)
  if (res.statusCode == 403) return Promise.resolve('')
  const location = res.headers.location
  return new Promise((ful, rej) => {
    https.get(location, (res) => {
      if (res.statusCode == 200) {
        mkdir(path.dirname(localFile))
          .then(() => {
            res.pipe(fs.createWriteStream(localFile))
            ful(res)
          })
          .catch(console.dir)
      } else {
        ful()
      }
    })
  })
}

router.get('/api/v1/crates/:name/:version/download', async (ctx) => {
  const name = ctx.params.name
  const version = ctx.params.version

  ctx.body = await getTar(name, version)
})

app.use(router.routes())
app.on('error', function(err, ctx) {
  console.log(err)
})

module.exports = app
