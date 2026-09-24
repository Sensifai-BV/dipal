from django.urls import get_resolver
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import render


def extract_urls_grouped_by_prefix():

    resolver = get_resolver()
    collected = {}

    def walk(patterns):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                walk(p.url_patterns)
            else:
                name = p.name
                if not name:
                    continue

                raw_path = "/" + str(p.pattern)
                path = raw_path.replace("^", "").replace("$", "").strip("/")


                if not path:
                    prefix = "root"
                else:
                    prefix = path.split("/")[0]

                collected.setdefault(prefix, {})
                collected[prefix][name] = "/" + path

    walk(resolver.url_patterns)
    return collected


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request, format=None):


    if request.accepted_renderer.format == "html":
        return render(request, "api_index.html")

    collected = extract_urls_grouped_by_prefix()


    absolute_groups = {}
    for prefix, urls in collected.items():
        absolute_groups[prefix] = {
            name: request.build_absolute_uri(path)
            for name, path in urls.items()
        }

    return Response({
        "message": "Welcome to the PhotoGear Backend API",
        "version": "v1",
        "endpoint_groups_count": len(absolute_groups),
        "endpoints": absolute_groups,
    })
