# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.contrib.auth import get_user_model
from django.conf import settings

from rest_framework.authtoken.models import Token
from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateAPIView, RetrieveUpdateDestroyAPIView,
    GenericAPIView
    )
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import (
    IsAuthenticated, IsAdminUser, BasePermission, SAFE_METHODS
    )
from rest_framework.decorators import detail_route
from rest_framework import status
from rest_framework.response import Response
from social_django.utils import load_strategy, load_backend
from requests_oauthlib import OAuth1Session
from django_filters import rest_framework as filters
from django_filters.widgets import BooleanWidget

from .serializers import (
    UserSerializer, SocialSignUpSerializer, MappingTeamSerializer
    )
from .models import MappingTeam

User = get_user_model()


class IsOwnerAdminOrReadOnly(BasePermission):
    """Object-level permission to only allow owners of an object to edit it."""

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in SAFE_METHODS:
            return True
        else:
            return obj.created_by == request.user or request.user.is_staff


class CurrentUserDetailAPIView(RetrieveUpdateAPIView):
    """
    get:
    Get details of the current logged user.
    patch:
    Update details of the current logged user.
    put:
    Update details of the current logged user.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer
    model = get_user_model()
    queryset = model.objects.all()

    def get_object(self, queryset=None):
        return self.request.user


class SocialAuthAPIView(GenericAPIView):
    """View that allows to authenticate in OSMCHA with an OpenStreetMap account.
    Send an empty `POST` request to receive the `oauth_token` and the
    `oauth_token_secret`. After authenticate in the OSM website, make another
    `POST` request sending the `oauth_token`, `oauth_token_secret` and the
    `oauth_verifier` to receive the `token` that you need to make authenticated
    requests in all OSMCHA endpoints.
    """
    queryset = User.objects.all()
    serializer_class = SocialSignUpSerializer

    base_url = 'https://www.openstreetmap.org/oauth'
    request_token_url = '{}/request_token?oauth_callback={}'.format(
        base_url,
        settings.OAUTH_REDIRECT_URI
        )
    access_token_url = '{}/access_token'.format(base_url)

    def get_access_token(self, oauth_token, oauth_token_secret, oauth_verifier):
        oauth = OAuth1Session(
            settings.SOCIAL_AUTH_OPENSTREETMAP_KEY,
            client_secret=settings.SOCIAL_AUTH_OPENSTREETMAP_SECRET,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
            verifier=oauth_verifier
            )
        return oauth.fetch_access_token(self.access_token_url)

    def get_user_token(self, request, access_token):
        backend = load_backend(
            strategy=load_strategy(request),
            name='openstreetmap',
            redirect_uri=None
            )
        authed_user = request.user if not request.user.is_anonymous else None
        user = backend.do_auth(access_token, user=authed_user)
        token, created = Token.objects.get_or_create(user=user)
        return {'token': token.key}

    def post(self, request, *args, **kwargs):
        if 'oauth_token' not in request.data.keys() or not request.data['oauth_token']:
            consumer = OAuth1Session(
                settings.SOCIAL_AUTH_OPENSTREETMAP_KEY,
                client_secret=settings.SOCIAL_AUTH_OPENSTREETMAP_SECRET
                )
            request_token = consumer.fetch_request_token(
                self.request_token_url
                )
            return Response({
                'oauth_token': request_token['oauth_token'],
                'oauth_token_secret': request_token['oauth_token_secret']
                })
        else:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            access_token = self.get_access_token(
                request.data['oauth_token'],
                request.data['oauth_token_secret'],
                request.data['oauth_verifier']
                )
            return Response(self.get_user_token(request, access_token))


class MappingTeamFilter(filters.FilterSet):
    trusted = filters.BooleanFilter(
        widget=BooleanWidget(),
        help_text="""Filter Mapping Teams that were trusted by a staff user."""
        )
    name = filters.CharFilter(
        name='name',
        lookup_expr='icontains',
        help_text="""Filter Mapping Teams by its name field using the icontains
            lookup expression."""
        )
    class Meta:
        model = MappingTeam
        fields = []


class MappingTeamListCreateAPIView(ListCreateAPIView):
    """List and create Mapping teams."""
    queryset = MappingTeam.objects.all()
    serializer_class = MappingTeamSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = MappingTeamFilter

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            )


class MappingTeamDetailAPIView(RetrieveUpdateDestroyAPIView):
    """List and create Mapping teams."""
    queryset = MappingTeam.objects.all()
    serializer_class = MappingTeamSerializer
    permission_classes = (IsAuthenticated, IsOwnerAdminOrReadOnly,)


class MappingTeamTrustingAPIView(ModelViewSet):
    queryset = MappingTeam.objects.all()
    serializer_class = MappingTeamSerializer
    permission_classes = (IsAdminUser,)

    def update_team(self, team, request, trusted):
        """Update 'checked', 'harmful', 'check_user', 'check_date' fields of the
        changeset and return a 200 response"""
        team.trusted = trusted
        team.save(
            update_fields=['trusted']
            )
        return Response(
            {'detail': 'Mapping Team set as {}.'.format('trusted' if trusted else 'untrusted')},
            status=status.HTTP_200_OK
            )

    @detail_route(methods=['put'])
    def set_trusted(self, request, pk):
        """Set a Mapping Team as trusted. You don't need to send data,
        just make an empty PUT request.
        """
        team = self.get_object()
        if team.trusted:
            return Response(
                {'detail': 'Mapping team is already trusted.'},
                status=status.HTTP_403_FORBIDDEN
                )
        return self.update_team(team, request, trusted=True)

    @detail_route(methods=['put'])
    def set_untrusted(self, request, pk):
        """Set a Mapping Team as untrusted. You don't need to send data,
        just make an empty PUT request.
        """
        team = self.get_object()
        if team.trusted == False:
            return Response(
                {'detail': 'Mapping team is already untrusted.'},
                status=status.HTTP_403_FORBIDDEN
                )
        return self.update_team(team, request, trusted=False)
