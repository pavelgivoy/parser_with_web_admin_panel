from starlette.middleware.cors import CORSMiddleware

MIDDLEWARES = [(CORSMiddleware, dict(allow_origins=('*',),
                                     allow_methods=("GET",),
                                     allow_headers=('*',), ))]
